/**
 * @file lowpass_filter_10hz.c
 * @brief 一阶IIR低通滤波器实现
 * @req REQ-001
 * @dal DAL-A
 * @misra MISRA-C:2012
 */

#define _USE_MATH_DEFINES
#include <math.h>
#include <stdbool.h>

/* [REQ-001] [MISRA-Rule-8.9] 静态全局变量 */
static double s_prev_output = 0.0;      /* 上次滤波输出 */
static bool s_fault_detected = false;   /* 故障检测标志 */
static double s_alpha = 0.0;            /* 滤波系数 */
static bool s_initialized = false;      /* 初始化标志 */

/* [REQ-001] [MISRA-Rule-8.4] 外部函数声明 */
void lowpass_filter_init(void);
double lowpass_filter_apply(double raw_input);
bool lowpass_filter_get_fault(void);

/**
 * @brief 初始化低通滤波器
 * @req REQ-001
 * @misra MISRA-Rule-15.7 单返回点
 */
void lowpass_filter_init(void) {
    /* [REQ-001] [MISRA-Rule-16.4] 显式初始化 */
    s_prev_output = 0.0;
    s_fault_detected = false;
    s_initialized = true;
    
    /* 计算滤波系数 alpha = 1 - exp(-2*PI*fc/fs) */
    /* fc=10Hz, fs=100Hz */
    s_alpha = 1.0 - exp(-2.0 * M_PI * 10.0 / 100.0);
}

/**
 * @brief 应用低通滤波器
 * @param raw_input 原始输入数据
 * @return 滤波后的输出数据
 * @req REQ-001
 * @misra MISRA-Rule-15.7 单返回点
 */
double lowpass_filter_apply(double raw_input) {
    double filtered_output;
    
    /* [REQ-001] [MISRA-Rule-14.3] 输入有效性检查 */
    if (raw_input < 0.0 || raw_input > 20000.0) {
        /* [REQ-001] 故障处理：输入超范围 */
        s_fault_detected = true;
        return 0.0;
    }
    
    /* [REQ-001] [MISRA-Rule-14.3] NaN/Inf检查 */
    if (isnan(raw_input) || isinf(raw_input)) {
        /* [REQ-001] 故障处理：无效输入 */
        s_fault_detected = true;
        return 0.0;
    }
    
    /* [REQ-001] [MISRA-Rule-15.7] 一阶IIR滤波算法 */
    /* y[n] = alpha * x[n] + (1-alpha) * y[n-1] */
    filtered_output = s_alpha * raw_input + (1.0 - s_alpha) * s_prev_output;
    
    /* [REQ-001] [MISRA-Rule-16.4] 输出范围检查 */
    if (filtered_output < 0.0) {
        filtered_output = 0.0;
    } else if (filtered_output > 20000.0) {
        filtered_output = 20000.0;
    }
    
    /* [REQ-001] [MISRA-Rule-16.4] 更新状态变量 */
    s_prev_output = filtered_output;
    
    return filtered_output;
}

/**
 * @brief 查询故障状态
 * @return true 如果检测到故障
 * @req REQ-001
 */
bool lowpass_filter_get_fault(void) {
    return s_fault_detected;
}
