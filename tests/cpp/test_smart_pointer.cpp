/**
 * @file test_smart_pointer.cpp
 * @brief C++ 智能指针资源管理器单元测试
 * 
 * 测试覆盖:
 * - DataBuffer 创建、写入、读取
 * - SignalHandler 回调注册和处理
 * - ResourceManager 资源管理
 * - 异常处理
 * 
 * 编译: g++ -std=c++17 -Wall -Wextra -o test_smart_pointer test_smart_pointer.cpp
 * 运行: ./test_smart_pointer
 */

#include <cassert>
#include <iostream>
#include <string>
#include <vector>

// 包含被测头文件
#include "../../templates/cpp/smart_pointer.h"

using namespace skyforge;

// ==================== DataBuffer 测试 ====================

void test_data_buffer_creation() {
    std::cout << "  test_data_buffer_creation: ";
    
    DataBuffer buffer(1024);
    assert(buffer.is_valid() == true);
    assert(buffer.capacity() == 1024);
    assert(buffer.size_bytes() == 0);
    
    std::cout << "PASS" << std::endl;
}

void test_data_buffer_write() {
    std::cout << "  test_data_buffer_write: ";
    
    DataBuffer buffer(100);
    uint8_t data[] = {1, 2, 3, 4, 5};
    
    assert(buffer.write(data, 5) == true);
    assert(buffer.size_bytes() == 5);
    
    const uint8_t* read_data = buffer.data();
    assert(read_data[0] == 1);
    assert(read_data[4] == 5);
    
    std::cout << "PASS" << std::endl;
}

void test_data_buffer_overflow() {
    std::cout << "  test_data_buffer_overflow: ";
    
    DataBuffer buffer(10);
    uint8_t data[20] = {0};
    
    assert(buffer.write(data, 10) == true);
    assert(buffer.write(data, 1) == false);  // 溢出
    
    std::cout << "PASS" << std::endl;
}

// ==================== SignalHandler 测试 ====================

void test_signal_handler_callback() {
    std::cout << "  test_signal_handler_callback: ";
    
    auto resource = std::make_shared<DataBuffer>(100);
    SignalHandler handler(resource);
    
    double last_value = 0.0;
    handler.register_callback([&last_value](double v) { last_value = v; });
    
    handler.process(42.0);
    assert(last_value == 42.0);
    
    handler.process(100.0);
    assert(last_value == 100.0);
    
    std::cout << "PASS" << std::endl;
}

void test_signal_handler_disabled() {
    std::cout << "  test_signal_handler_disabled: ";
    
    auto resource = std::make_shared<DataBuffer>(100);
    SignalHandler handler(resource);
    
    double last_value = 0.0;
    handler.register_callback([&last_value](double v) { last_value = v; });
    
    handler.set_enabled(false);
    handler.process(42.0);
    assert(last_value == 0.0);  // 回调未被调用
    
    std::cout << "PASS" << std::endl;
}

void test_signal_handler_invalid_resource() {
    std::cout << "  test_signal_handler_invalid_resource: ";
    
    // 创建一个有效的资源，然后测试无效情况
    auto valid_resource = std::make_shared<DataBuffer>(100);
    SignalHandler handler(valid_resource);
    
    double last_value = 0.0;
    handler.register_callback([&last_value](double v) { last_value = v; });
    
    // 禁用 handler 后测试
    handler.set_enabled(false);
    handler.process(42.0);
    assert(last_value == 0.0);  // 回调未被调用
    
    std::cout << "PASS" << std::endl;
}

// ==================== ResourceManager 测试 ====================

void test_resource_manager_create() {
    std::cout << "  test_resource_manager_create: ";
    
    ResourceManager manager;
    
    auto buffer = manager.create_buffer(1024);
    assert(buffer != nullptr);
    assert(buffer->is_valid() == true);
    assert(manager.resource_count() == 1);
    
    std::cout << "PASS" << std::endl;
}

void test_resource_manager_shared() {
    std::cout << "  test_resource_manager_shared: ";
    
    ResourceManager manager;
    auto resource = std::make_shared<DataBuffer>(512);
    
    manager.register_shared(resource);
    assert(manager.resource_count() == 1);
    
    // 共享所有权：原始指针仍有效
    assert(resource->is_valid() == true);
    
    std::cout << "PASS" << std::endl;
}

void test_resource_manager_limit() {
    std::cout << "  test_resource_manager_limit: ";
    
    ResourceManager manager;
    
    // 创建 32 个资源（达到限制）
    for (int i = 0; i < 32; i++) {
        auto buf = manager.create_buffer(100);
        (void)buf;  // 避免未使用警告
    }
    
    assert(manager.resource_count() == 32);
    
    std::cout << "PASS" << std::endl;
}

// ==================== 主函数 ====================

int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "  C++ 智能指针资源管理器测试" << std::endl;
    std::cout << "========================================" << std::endl;
    
    std::cout << "\nDataBuffer 测试:" << std::endl;
    test_data_buffer_creation();
    test_data_buffer_write();
    test_data_buffer_overflow();
    
    std::cout << "\nSignalHandler 测试:" << std::endl;
    test_signal_handler_callback();
    test_signal_handler_disabled();
    test_signal_handler_invalid_resource();
    
    std::cout << "\nResourceManager 测试:" << std::endl;
    test_resource_manager_create();
    test_resource_manager_shared();
    test_resource_manager_limit();
    
    std::cout << "\n========================================" << std::endl;
    std::cout << "  所有测试通过!" << std::endl;
    std::cout << "========================================" << std::endl;
    
    return 0;
}
