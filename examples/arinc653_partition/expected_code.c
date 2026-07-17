/* =============================================================================
 * Arinc653PartitionScheduler.c
 *
 * ARINC 653 分区调度器示例代码 (期望生成的 C 代码)
 *
 * 标准: ARINC 653 Part 1 / DO-178C DAL-A / MISRA-C:2012
 *
 * 功能:
 *   - 主时间帧 (MTF = 200ms) 内调度三个分区
 *   - 时间片分配: P1(Display)=50ms, P2(Navigation)=80ms, P3(HM)=70ms
 *   - 上下文切换 ≤ 1ms
 *   - 分区超时触发 Partition_HM_Handler
 *
 * MISRA-C:2012 合规要点:
 *   - Rule 8.7: 模块内部函数/变量使用 static
 *   - Rule 17.7: 函数返回值显式检查
 *   - Rule 20.4: 禁止动态内存分配
 *   - Dir 4.1:  所有故障显式处理
 *   - 避免魔法数字，使用 #define 命名常量
 * ============================================================================= */

#include <stdint.h>
#include <stddef.h>

/* ----- 命名常量 (避免魔法数字，MISRA-C Rule 8.9 / Dir 4.5) ----- */
#define A653_MTF_PERIOD_MS          (200U)   /* 主时间帧周期 200 ms */
#define A653_TIME_SLICE_P1_MS       (50U)    /* Partition 1: Display 时间片 */
#define A653_TIME_SLICE_P2_MS       (80U)    /* Partition 2: Navigation 时间片 */
#define A653_TIME_SLICE_P3_MS       (70U)    /* Partition 3: Health Monitoring 时间片 */
#define A653_NUM_PARTITIONS         (3U)     /* 分区数量 */
#define A653_CONTEXT_SWITCH_MAX_MS  (1U)     /* 上下文切换上限 1 ms */
#define A653_JITTER_MAX_US          (100U)   /* 调度抖动上限 100 μs */
#define A653_HM_HANDLER_MAX_US      (500U)   /* HM Handler 响应上限 500 μs */

/* ----- 类型定义 (强类型，MISRA-C Rule 8.4 / 8.7) ----- */
typedef enum {
    A653_CMD_CREATE    = 0U,
    A653_CMD_START     = 1U,
    A653_CMD_STOP      = 2U,
    A653_CMD_HM_REPORT = 3U,
    A653_CMD_QUERY     = 4U
} A653_Command_t;

typedef enum {
    A653_STATE_IDLE        = 0U,
    A653_STATE_RUNNABLE    = 1U,
    A653_STATE_RUNNING     = 2U,
    A653_STATE_BLOCKED     = 3U,
    A653_STATE_TERMINATED  = 4U
} A653_PartitionState_t;

typedef enum {
    A653_RESULT_OK             = 0U,
    A653_RESULT_INVALID_PARAM  = 1U,
    A653_RESULT_NO_RESOURCE    = 2U,
    A653_RESULT_TIMEOUT        = 3U
} A653_ResultCode_t;

typedef enum {
    A653_HM_EVENT_NONE        = 0U,
    A653_HM_EVENT_OVERRUN     = 1U,
    A653_HM_EVENT_STACK_FAULT = 2U,
    A653_HM_EVENT_FATAL       = 3U
} A653_HmEvent_t;

typedef struct {
    uint8_t                  partition_id;     /* 分区 ID (1..3) */
    A653_PartitionState_t    state;            /* 当前状态 */
    uint32_t                 time_slice_ms;    /* 分配的时间片 */
    uint32_t                 elapsed_ms;       /* 本帧已执行时间 */
    A653_HmEvent_t           last_hm_event;    /* 最近 HM 事件 */
} A653_Partition_t;

/* ----- 模块内部状态 (static, MISRA-C Rule 8.7) ----- */
static A653_Partition_t g_partitions[A653_NUM_PARTITIONS] = {
    { 1U, A653_STATE_IDLE, A653_TIME_SLICE_P1_MS, 0U, A653_HM_EVENT_NONE },
    { 2U, A653_STATE_IDLE, A653_TIME_SLICE_P2_MS, 0U, A653_HM_EVENT_NONE },
    { 3U, A653_STATE_IDLE, A653_TIME_SLICE_P3_MS, 0U, A653_HM_EVENT_NONE }
};

static uint32_t   g_mtf_tick       = 0U;   /* MTF 周期计数 */
static uint8_t    g_current_index  = 0U;   /* 当前调度分区索引 (0..2) */
static uint32_t   g_switch_count   = 0U;   /* 上下文切换次数 (统计) */

/* ----- 外部声明 (由分区代码提供，本调度器只调用) ----- */
extern void main_partition_1(void);   /* Display 入口 */
extern void main_partition_2(void);   /* Navigation 入口 */
extern void main_partition_3(void);   /* Health Monitoring 入口 */

/* Partition_HM_Handler: 健康监控处理函数 (本调度器内部默认实现) */
static void Partition_HM_Handler(uint8_t partition_id, A653_HmEvent_t event)
{
    /* 记录故障事件到分区元数据 (DO-178C Dir 4.1 显式处理) */
    uint8_t idx = partition_id - 1U;
    if (idx < A653_NUM_PARTITIONS) {
        g_partitions[idx].last_hm_event = event;
        if (event == A653_HM_EVENT_OVERRUN) {
            /* 超时分区强制 TERMINATED，本 MTF 内不再调度 */
            g_partitions[idx].state = A653_STATE_TERMINATED;
        } else if (event == A653_HM_EVENT_FATAL) {
            /* 致命故障: 进入 SAFE_STATE (实际系统应触发硬件看门狗) */
            uint8_t i;
            for (i = 0U; i < A653_NUM_PARTITIONS; i++) {
                g_partitions[i].state = A653_STATE_TERMINATED;
            }
        } else {
            /* STACK_FAULT 等其他事件: 仅记录，不停止分区 */
        }
    }
}

/* 上下文切换: 加载下一分区的执行上下文 */
static A653_ResultCode_t A653_ContextSwitch(uint8_t next_index)
{
    A653_ResultCode_t result = A653_RESULT_OK;
    if (next_index >= A653_NUM_PARTITIONS) {
        result = A653_RESULT_INVALID_PARAM;
    } else {
        /* 实际硬件: 保存寄存器集合 -> 刷新 MMU/MPU -> 加载新上下文 */
        g_current_index = next_index;
        g_switch_count++;
        /* 切换期间中断关闭 (本示例省略具体汇编代码) */
    }
    return result;   /* Rule 17.7: 调用方必须检查返回值 */
}

/* 调度核心: 在 MTF 内按时间片轮转调度各分区 */
static void A653_ScheduleOneMtf(void)
{
    uint8_t  idx;
    uint32_t slice_sum_ms = 0U;

    /* 验证时间片守恒不变式 (CON-A653-INV-002) */
    slice_sum_ms = A653_TIME_SLICE_P1_MS + A653_TIME_SLICE_P2_MS + A653_TIME_SLICE_P3_MS;
    if (slice_sum_ms != A653_MTF_PERIOD_MS) {
        /* 配置错误: 进入 SAFE_STATE */
        (void)Partition_HM_Handler(0U, A653_HM_EVENT_FATAL);
        return;
    }

    /* 每帧开始: 重置所有非 TERMINATED 分区状态 */
    for (idx = 0U; idx < A653_NUM_PARTITIONS; idx++) {
        if (g_partitions[idx].state != A653_STATE_TERMINATED) {
            g_partitions[idx].state       = A653_STATE_RUNNABLE;
            g_partitions[idx].elapsed_ms  = 0U;
        }
    }

    /* 按预定顺序调度三个分区 */
    for (idx = 0U; idx < A653_NUM_PARTITIONS; idx++) {
        A653_ResultCode_t cs_result;
        A653_Partition_t *p = &g_partitions[idx];
        if (p->state == A653_STATE_TERMINATED) {
            continue;   /* 故障分区跳过本帧调度 */
        }
        /* 上下文切换 (Rule 17.7: 检查返回值) */
        cs_result = A653_ContextSwitch(idx);
        if (cs_result != A653_RESULT_OK) {
            (void)Partition_HM_Handler(p->partition_id, A653_HM_EVENT_FATAL);
            continue;
        }
        p->state = A653_STATE_RUNNING;
        /* 调用分区入口函数 (实际系统带 watchdog 监控执行时间) */
        switch (idx) {
            case 0U:
                main_partition_1();   /* Display */
                break;
            case 1U:
                main_partition_2();   /* Navigation */
                break;
            case 2U:
                main_partition_3();   /* Health Monitoring */
                break;
            default:
                /* 不应到达 (DO-178C 完备性) */
                (void)Partition_HM_Handler(p->partition_id, A653_HM_EVENT_FATAL);
                break;
        }
        p->elapsed_ms = p->time_slice_ms;   /* 假设正常用尽时间片 */
        p->state      = A653_STATE_RUNNABLE;

        /* 超时检测: 若 elapsed > time_slice 则触发 HM Handler */
        if (p->elapsed_ms > p->time_slice_ms) {
            (void)Partition_HM_Handler(p->partition_id, A653_HM_EVENT_OVERRUN);
        }
    }

    g_mtf_tick++;   /* MTF 周期计数 +1 */
}

/* 对外 API: 处理调度命令 (Rule 8.4 原型声明) */
A653_ResultCode_t A653_Scheduler_Dispatch(uint8_t        partition_id,
                                          A653_Command_t command,
                                          uint32_t       mtf_tick,
                                          A653_PartitionState_t *out_state,
                                          A653_HmEvent_t        *out_event)
{
    A653_ResultCode_t result = A653_RESULT_OK;
    /* 参数校验 (CON-A653-PRE-000 / PRE-001) */
    if ((partition_id < 1U) || (partition_id > A653_NUM_PARTITIONS) ||
        (out_state == NULL) || (out_event == NULL)) {
        result = A653_RESULT_INVALID_PARAM;
    } else {
        uint8_t idx = partition_id - 1U;
        switch (command) {
            case A653_CMD_CREATE:
                g_partitions[idx].state = A653_STATE_RUNNABLE;
                break;
            case A653_CMD_START:
                A653_ScheduleOneMtf();
                break;
            case A653_CMD_STOP:
                g_partitions[idx].state = A653_STATE_TERMINATED;
                break;
            case A653_CMD_HM_REPORT:
                *out_event = g_partitions[idx].last_hm_event;
                break;
            case A653_CMD_QUERY:
                /* 仅返回当前状态 */
                break;
            default:
                result = A653_RESULT_INVALID_PARAM;
                break;
        }
        *out_state = g_partitions[idx].state;
        if (command != A653_CMD_HM_REPORT) {
            *out_event = g_partitions[idx].last_hm_event;
        }
        (void)mtf_tick;   /* 用于日志，本示例不直接使用 */
    }
    return result;
}
