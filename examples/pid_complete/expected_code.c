/**
 * @file pid_controller.c
 * @brief 增量式PID控制器实现
 * @req REQ-001
 * @dal DAL-B
 * @misra MISRA-C:2012
 */

#include <math.h>
#include <stdbool.h>

/* [REQ-001] [MISRA-Rule-8.9] PID参数（静态全局变量） */
static double s_kp = 1.0;           /* 比例系数 */
static double s_ki = 0.1;           /* 积分系数 */
static double s_kd = 0.01;          /* 微分系数 */
static double s_integral = 0.0;     /* 积分项 */
static double s_prev_error = 0.0;   /* 上次误差 */
static double s_prev_prev_error = 0.0; /* 上上次误差 */
static double s_integral_max = 1000.0; /* 积分限幅 */
static bool s_initialized = false;  /* 初始化标志 */

/* [REQ-001] [MISRA-Rule-8.4] 外部函数声明 */
void pid_controller_init(double kp, double ki, double kd);
double pid_controller_update(double setpoint, double actual);
void pid_controller_reset(void);

/**
 * @brief 初始化PID控制器
 * @param kp 比例系数
 * @param ki 积分系数
 * @param kd 微分系数
 * @req REQ-001
 * @misra MISRA-Rule-15.7 单返回点
 */
void pid_controller_init(double kp, double ki, double kd) {
    /* [REQ-001] [MISRA-Rule-16.4] 参数范围检查 */
    if (kp < 0.1) kp = 0.1;
    if (kp > 10.0) kp = 10.0;
    if (ki < 0.01) ki = 0.01;
    if (ki > 1.0) ki = 1.0;
    if (kd < 0.001) kd = 0.001;
    if (kd > 0.1) kd = 0.1;
    
    /* [REQ-001] [MISRA-Rule-16.4] 显式初始化 */
    s_kp = kp;
    s_ki = ki;
    s_kd = kd;
    s_integral = 0.0;
    s_prev_error = 0.0;
    s_prev_prev_error = 0.0;
    s_initialized = true;
}

/**
 * @brief PID控制器更新
 * @param setpoint 目标值
 * @param actual 实际值
 * @return 控制输出
 * @req REQ-001
 * @misra MISRA-Rule-15.7 单返回点
 */
double pid_controller_update(double setpoint, double actual) {
    double error, delta_error, output;
    
    /* [REQ-001] [MISRA-Rule-14.3] 输入有效性检查 */
    if (setpoint < 0.0) setpoint = 0.0;
    if (setpoint > 10000.0) setpoint = 10000.0;
    if (actual < 0.0) actual = 0.0;
    if (actual > 10000.0) actual = 10000.0;
    
    /* 计算误差 */
    error = setpoint - actual;
    
    /* 计算增量 */
    delta_error = error - s_prev_error;
    
    /* 增量式PID算法 */
    /* Δu = Kp*(e[n]-e[n-1]) + Ki*e[n] + Kd*(e[n]-2*e[n-1]+e[n-2]) */
    output = s_kp * delta_error + s_ki * error + s_kd * (error - 2.0 * s_prev_error + s_prev_prev_error);
    
    /* [REQ-001] [MISRA-Rule-16.4] 积分限幅（抗饱和） */
    s_integral += error;
    if (s_integral > s_integral_max) {
        s_integral = s_integral_max;
    } else if (s_integral < -s_integral_max) {
        s_integral = -s_integral_max;
    }
    
    /* 更新历史误差 */
    s_prev_prev_error = s_prev_error;
    s_prev_error = error;
    
    /* [REQ-001] [MISRA-Rule-16.4] 输出范围检查 */
    if (output < 0.0) {
        output = 0.0;
    } else if (output > 1000.0) {
        output = 1000.0;
    }
    
    return output;
}

/**
 * @brief 复位PID控制器
 * @req REQ-001
 */
void pid_controller_reset(void) {
    s_integral = 0.0;
    s_prev_error = 0.0;
    s_prev_prev_error = 0.0;
}
