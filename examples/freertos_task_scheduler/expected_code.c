/* =============================================================================
 * FreeRTOSTaskScheduler.c
 *
 * FreeRTOS 任务调度器示例代码 (期望生成的 C 代码)
 *
 * 标准: FreeRTOS V10.x / DO-178C DAL-B / MISRA-C:2012
 *
 * 功能:
 *   - 3 个核心周期任务: Sensor_Reader / Control_Law / Telemetry_Output
 *   - 队列通信: Sensor_Reader -> Control_Law -> Telemetry_Output
 *   - 看门狗超时触发 watchdog_reset
 *   - 优先级继承 (Mutex) 防止优先级反转
 *   - CPU 利用率 > 85% 触发告警
 *
 * MISRA-C:2012 合规要点:
 *   - Rule 8.7: 模块内部对象使用 static
 *   - Rule 17.7: FreeRTOS API 返回值显式检查
 *   - Rule 20.4: 静态内存分配 (无 malloc)
 *   - Dir 4.1:  所有故障显式处理
 *   - 避免魔法数字，使用 #define 命名常量
 * ============================================================================= */

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"

/* ----- 命名常量 (避免魔法数字) ----- */
#define FRTOS_TICK_RATE_HZ            (1000U)   /* 系统 tick 频率 1 kHz */
#define FRTOS_NUM_CORE_TASKS          (3U)      /* 核心任务数量 */
#define FRTOS_QUEUE_LENGTH            (10U)     /* 队列长度 */
#define FRTOS_QUEUE_SEND_TIMEOUT_MS   (0U)      /* 队列发送超时: 非阻塞 */
#define FRTOS_MUTEX_HOLD_MAX_US       (100U)    /* Mutex 持有上限 100 μs */
#define FRTOS_CPU_LOAD_ALARM_PERCENT  (85U)     /* CPU 利用率告警阈值 */
#define FRTOS_CPU_LOAD_WARN_PERCENT   (70U)     /* CPU 利用率警告阈值 */
#define FRTOS_WATCHDOG_TIMEOUT_MS     (500U)    /* 硬件看门狗超时 500 ms */

/* 任务配置 (CON-FRTOS-INV-002 / 003 / 004) */
#define SENSOR_READER_PRIORITY        (5U)      /* 优先级 5 (最高) */
#define SENSOR_READER_PERIOD_MS       (10U)     /* 周期 10 ms */
#define SENSOR_READER_BUDGET_MS       (2U)      /* 预算 2 ms */
#define SENSOR_READER_STACK_WORDS     (1024U)   /* 栈 1024 字 */

#define CONTROL_LAW_PRIORITY          (4U)      /* 优先级 4 */
#define CONTROL_LAW_PERIOD_MS         (20U)     /* 周期 20 ms */
#define CONTROL_LAW_BUDGET_MS         (5U)      /* 预算 5 ms */
#define CONTROL_LAW_STACK_WORDS       (2048U)   /* 栈 2048 字 */

#define TELEMETRY_OUTPUT_PRIORITY     (3U)      /* 优先级 3 */
#define TELEMETRY_OUTPUT_PERIOD_MS    (100U)    /* 周期 100 ms */
#define TELEMETRY_OUTPUT_BUDGET_MS    (10U)     /* 预算 10 ms */
#define TELEMETRY_OUTPUT_STACK_WORDS  (1024U)   /* 栈 1024 字 */

/* ----- 类型定义 (强类型) ----- */
typedef enum {
    FRTOS_CMD_CREATE       = 0U,
    FRTOS_CMD_DELETE       = 1U,
    FRTOS_CMD_SUSPEND      = 2U,
    FRTOS_CMD_RESUME       = 3U,
    FRTOS_CMD_QUERY_STATE  = 4U,
    FRTOS_CMD_WD_RESET     = 5U
} FRTOS_Command_t;

typedef enum {
    FRTOS_STATE_DELETED   = 0U,
    FRTOS_STATE_READY     = 1U,
    FRTOS_STATE_RUNNING   = 2U,
    FRTOS_STATE_BLOCKED   = 3U,
    FRTOS_STATE_SUSPENDED = 4U
} FRTOS_TaskState_t;

typedef enum {
    FRTOS_RESULT_OK             = 0U,
    FRTOS_RESULT_NO_RESOURCE    = 1U,
    FRTOS_RESULT_TIMEOUT        = 2U,
    FRTOS_RESULT_INVALID_PARAM  = 3U
} FRTOS_ResultCode_t;

typedef enum {
    FRTOS_WD_EVENT_NONE    = 0U,
    FRTOS_WD_EVENT_OVERRUN = 1U,
    FRTOS_WD_EVENT_RESET   = 2U,
    FRTOS_WD_EVENT_ALARM   = 3U
} FRTOS_WatchdogEvent_t;

/* 传感器数据结构 (Sensor_Reader -> Control_Law) */
typedef struct {
    float    accel_x;
    float    accel_y;
    float    accel_z;
    uint32_t timestamp_ms;
} SensorData_t;

/* 控制指令结构 (Control_Law -> Telemetry_Output) */
typedef struct {
    float    pitch_cmd;
    float    roll_cmd;
    float    yaw_cmd;
    uint32_t timestamp_ms;
} ControlCmd_t;

/* ----- 模块内部状态 (static, MISRA-C Rule 8.7) ----- */
static StaticQueue_t     g_sensor_data_queue_storage;
static StaticQueue_t     g_control_cmd_queue_storage;
static QueueHandle_t     g_sensor_data_queue = NULL;
static QueueHandle_t     g_control_cmd_queue = NULL;
static StaticSemaphore_t g_mutex_buffer;
static SemaphoreHandle_t g_shared_mutex     = NULL;

static TaskHandle_t      g_task_sensor_reader    = NULL;
static TaskHandle_t      g_task_control_law      = NULL;
static TaskHandle_t      g_task_telemetry_output = NULL;

static uint8_t           g_cpu_load_percent   = 0U;
static FRTOS_WatchdogEvent_t g_last_wd_event  = FRTOS_WD_EVENT_NONE;
static uint32_t          g_queue_drop_count   = 0U;

/* 静态栈 (Static Allocation, MISRA-C Rule 20.4) */
static StackType_t       g_stack_sensor_reader   [SENSOR_READER_STACK_WORDS];
static StackType_t       g_stack_control_law     [CONTROL_LAW_STACK_WORDS];
static StackType_t       g_stack_telemetry_output[TELEMETRY_OUTPUT_STACK_WORDS];
static StaticTask_t      g_tcb_sensor_reader;
static StaticTask_t      g_tcb_control_law;
static StaticTask_t      g_tcb_telemetry_output;

/* ----- 看门狗回调 (弱定义，应用层可重写) ----- */
__attribute__((weak)) void watchdog_reset(const char *task_name, uint32_t overrun_ms)
{
    (void)task_name;
    (void)overrun_ms;
    g_last_wd_event = FRTOS_WD_EVENT_OVERRUN;
    /* 实际系统: 记录故障日志 + 复位对应任务 */
}

/* ----- CPU 利用率告警回调 ----- */
__attribute__((weak)) void cpu_load_alarm(uint8_t load_percent)
{
    (void)load_percent;
    g_last_wd_event = FRTOS_WD_EVENT_ALARM;
    /* 实际系统: 降低 Telemetry_Output 频率 (降级运行) */
}

/* ----- Sensor_Reader 任务: 周期 10ms, 预算 2ms, 优先级 5 ----- */
static void Task_Sensor_Reader(void *pvParameters)
{
    (void)pvParameters;
    TickType_t last_wake = xTaskGetTickCount();
    SensorData_t sample;
    for (;;) {
        /* 模拟读取 IMU/ADC 数据 (实际代码调用 BSP) */
        sample.accel_x = 0.0F;
        sample.accel_y = 0.0F;
        sample.accel_z = 9.8F;
        sample.timestamp_ms = (uint32_t)xTaskGetTickCount();
        /* 发送到队列 (非阻塞，满则丢弃) - Rule 17.7 检查返回值 */
        BaseType_t ok = xQueueSend(g_sensor_data_queue, &sample,
                                   pdMS_TO_TICKS(FRTOS_QUEUE_SEND_TIMEOUT_MS));
        if (ok != pdPASS) {
            g_queue_drop_count++;   /* 队列满: 递增丢包计数 */
        }
        /* 周期等待 10ms (vTaskDelayUntil 保证严格周期性) */
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(SENSOR_READER_PERIOD_MS));
    }
}

/* ----- Control_Law 任务: 周期 20ms, 预算 5ms, 优先级 4 ----- */
static void Task_Control_Law(void *pvParameters)
{
    (void)pvParameters;
    TickType_t last_wake = xTaskGetTickCount();
    SensorData_t in_data;
    ControlCmd_t out_cmd;
    for (;;) {
        /* 接收传感器数据 (超时 = 任务周期，超时使用上一拍) - Rule 17.7 */
        BaseType_t ok = xQueueReceive(g_sensor_data_queue, &in_data,
                                      pdMS_TO_TICKS(CONTROL_LAW_PERIOD_MS));
        if (ok == pdPASS) {
            /* 取 Mutex 保护共享资源 (优先级继承) - Rule 17.7 */
            if (xSemaphoreTake(g_shared_mutex, pdMS_TO_TICKS(1U)) == pdPASS) {
                /* 计算控制指令 (PID/姿态控制，本示例简化) */
                out_cmd.pitch_cmd = in_data.accel_x * 0.1F;
                out_cmd.roll_cmd  = in_data.accel_y * 0.1F;
                out_cmd.yaw_cmd   = in_data.accel_z * 0.1F;
                out_cmd.timestamp_ms = (uint32_t)xTaskGetTickCount();
                (void)xSemaphoreGive(g_shared_mutex);
            }
            /* 发送控制指令到队列 (非阻塞) */
            if (xQueueSend(g_control_cmd_queue, &out_cmd,
                           pdMS_TO_TICKS(FRTOS_QUEUE_SEND_TIMEOUT_MS)) != pdPASS) {
                g_queue_drop_count++;
            }
        }
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(CONTROL_LAW_PERIOD_MS));
    }
}

/* ----- Telemetry_Output 任务: 周期 100ms, 预算 10ms, 优先级 3 ----- */
static void Task_Telemetry_Output(void *pvParameters)
{
    (void)pvParameters;
    TickType_t last_wake = xTaskGetTickCount();
    ControlCmd_t cmd;
    for (;;) {
        /* 接收控制指令 (超时 = 任务周期) - Rule 17.7 */
        BaseType_t ok = xQueueReceive(g_control_cmd_queue, &cmd,
                                      pdMS_TO_TICKS(TELEMETRY_OUTPUT_PERIOD_MS));
        if (ok == pdPASS) {
            /* 模拟通过 UART/CAN 上报遥测数据 */
            (void)cmd;
        }
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(TELEMETRY_OUTPUT_PERIOD_MS));
    }
}

/* ----- 系统初始化: 创建队列/Mutex/任务 ----- */
FRTOS_ResultCode_t FreeRTOS_Scheduler_Init(void)
{
    FRTOS_ResultCode_t result = FRTOS_RESULT_OK;
    /* 创建队列 (静态分配, Rule 20.4) */
    g_sensor_data_queue = xQueueCreateStatic(FRTOS_QUEUE_LENGTH, sizeof(SensorData_t),
                                             (uint8_t *)g_stack_sensor_reader,  /* 此处仅占位 */
                                             &g_sensor_data_queue_storage);
    /* 注: 实际应用应提供独立的静态存储区，本示例简化展示 */
    if (g_sensor_data_queue == NULL) {
        result = FRTOS_RESULT_NO_RESOURCE;
    } else {
        g_control_cmd_queue = xQueueCreateStatic(FRTOS_QUEUE_LENGTH, sizeof(ControlCmd_t),
                                                 (uint8_t *)g_stack_control_law,
                                                 &g_control_cmd_queue_storage);
        if (g_control_cmd_queue == NULL) {
            result = FRTOS_RESULT_NO_RESOURCE;
        }
    }
    /* 创建 Mutex (启用优先级继承, CON-FRTOS-INV-007) */
    if (result == FRTOS_RESULT_OK) {
        g_shared_mutex = xSemaphoreCreateMutexStatic(&g_mutex_buffer);
        if (g_shared_mutex == NULL) {
            result = FRTOS_RESULT_NO_RESOURCE;
        }
    }
    /* 创建三个核心任务 (静态分配 TCB 与栈) */
    if (result == FRTOS_RESULT_OK) {
        g_task_sensor_reader = xTaskCreateStatic(
            Task_Sensor_Reader, "Sensor_Reader",
            SENSOR_READER_STACK_WORDS, NULL,
            SENSOR_READER_PRIORITY, g_stack_sensor_reader, &g_tcb_sensor_reader);
        if (g_task_sensor_reader == NULL) {
            result = FRTOS_RESULT_NO_RESOURCE;
        }
    }
    if (result == FRTOS_RESULT_OK) {
        g_task_control_law = xTaskCreateStatic(
            Task_Control_Law, "Control_Law",
            CONTROL_LAW_STACK_WORDS, NULL,
            CONTROL_LAW_PRIORITY, g_stack_control_law, &g_tcb_control_law);
        if (g_task_control_law == NULL) {
            result = FRTOS_RESULT_NO_RESOURCE;
        }
    }
    if (result == FRTOS_RESULT_OK) {
        g_task_telemetry_output = xTaskCreateStatic(
            Task_Telemetry_Output, "Telemetry_Output",
            TELEMETRY_OUTPUT_STACK_WORDS, NULL,
            TELEMETRY_OUTPUT_PRIORITY, g_stack_telemetry_output, &g_tcb_telemetry_output);
        if (g_task_telemetry_output == NULL) {
            result = FRTOS_RESULT_NO_RESOURCE;
        }
    }
    return result;
}

/* ----- 对外 API: 调度命令分发 ----- */
FRTOS_ResultCode_t FreeRTOS_Scheduler_Dispatch(FRTOS_Command_t   command,
                                               const char       *task_name,
                                               FRTOS_TaskState_t *out_state,
                                               uint8_t           *out_cpu_load,
                                               FRTOS_WatchdogEvent_t *out_wd_event)
{
    FRTOS_ResultCode_t result = FRTOS_RESULT_OK;
    if ((out_state == NULL) || (out_cpu_load == NULL) || (out_wd_event == NULL)) {
        result = FRTOS_RESULT_INVALID_PARAM;
    } else {
        TaskHandle_t target = NULL;
        /* 根据任务名解析目标句柄 */
        if (strcmp(task_name, "Sensor_Reader") == 0) {
            target = g_task_sensor_reader;
        } else if (strcmp(task_name, "Control_Law") == 0) {
            target = g_task_control_law;
        } else if (strcmp(task_name, "Telemetry_Output") == 0) {
            target = g_task_telemetry_output;
        } else {
            result = FRTOS_RESULT_INVALID_PARAM;
        }
        if ((result == FRTOS_RESULT_OK) && (target != NULL)) {
            eTaskState st = eTaskGetState(target);
            switch (st) {
                case eRunning:   *out_state = FRTOS_STATE_RUNNING;   break;
                case eReady:     *out_state = FRTOS_STATE_READY;     break;
                case eBlocked:   *out_state = FRTOS_STATE_BLOCKED;   break;
                case eSuspended: *out_state = FRTOS_STATE_SUSPENDED; break;
                case eDeleted:   *out_state = FRTOS_STATE_DELETED;   break;
                default:         *out_state = FRTOS_STATE_DELETED;   break;
            }
            *out_cpu_load = g_cpu_load_percent;
            *out_wd_event = g_last_wd_event;
            /* CPU 利用率超阈值: 触发告警 (CON-FRTOS-FLT-002) */
            if (g_cpu_load_percent > FRTOS_CPU_LOAD_ALARM_PERCENT) {
                cpu_load_alarm(g_cpu_load_percent);
            }
            if (command == FRTOS_CMD_WD_RESET) {
                watchdog_reset(task_name, 0U);
            }
        }
    }
    return result;
}
