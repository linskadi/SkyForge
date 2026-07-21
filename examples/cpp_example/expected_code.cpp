/* [REQ-001] [MISRA-Rule-2.5] 低通滤波器模块实现 */
#pragma once

#include <cstdint>
#include <cmath>

/* [REQ-001] [MISRA-Rule-6.1] 使用 fixed-width 类型 */
using float32_t = float;

/* [REQ-001] [MISRA-Rule-15.1] 类定义 */
class LowPassFilter {
public:
    /* [REQ-001] [MISRA-Rule-15.2] 构造函数 */
    LowPassFilter() noexcept;
    
    /* [REQ-001] [MISRA-Rule-15.6] 处理函数 */
    double apply(double raw_input) noexcept;
    
    /* [REQ-001] [MISRA-Rule-15.6] 状态查询 */
    bool get_fault() const noexcept;
    
    /* [REQ-001] [MISRA-Rule-15.6] 初始化 */
    void init() noexcept;

private:
    /* [REQ-001] [MISRA-Rule-8.9] 成员变量 */
    double m_prev_output = 0.0;
    bool m_fault_detected = false;
    double m_alpha = 0.0;
};

/* [REQ-001] [MISRA-Rule-15.2] 构造函数实现 */
LowPassFilter::LowPassFilter() noexcept
    : m_prev_output(0.0), m_fault_detected(false) {
    /* 计算滤波系数 alpha = 1 - exp(-2*PI*fc/fs) */
    m_alpha = 1.0 - std::exp(-2.0 * M_PI * 10.0 / 100.0);
}

/* [REQ-001] [MISRA-Rule-15.6] 初始化函数 */
void LowPassFilter::init() noexcept {
    m_prev_output = 0.0;
    m_fault_detected = false;
}

/* [REQ-001] [MISRA-Rule-15.6] 处理函数 */
double LowPassFilter::apply(double raw_input) noexcept {
    /* [REQ-001] [MISRA-Rule-14.3] 输入有效性检查 */
    if (raw_input < 0.0 || raw_input > 20000.0) {
        m_fault_detected = true;
        return 0.0;
    }
    
    /* [REQ-001] [MISRA-Rule-15.7] 一阶IIR滤波算法 */
    double output = m_alpha * raw_input + (1.0 - m_alpha) * m_prev_output;
    
    /* [REQ-001] [MISRA-Rule-16.4] 更新状态变量 */
    m_prev_output = output;
    
    return output;
}

/* [REQ-001] [MISRA-Rule-15.6] 状态查询 */
bool LowPassFilter::get_fault() const noexcept {
    return m_fault_detected;
}
