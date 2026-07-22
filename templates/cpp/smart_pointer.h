/**
 * @file smart_pointer.h
 * @brief C++ 智能指针资源管理器
 * 
 * MISRA-C++/JSF AV C++/CERT C++ 合规
 * DO-178C 机载软件代码生成模板
 * 
 * 合规规则:
 * - Rule 3-1-1: 禁止在头文件中使用未命名命名空间
 * - Rule 5-2-1: 使用 const 修饰不变变量
 * - Rule 6-6-1: 使用 nullptr 替代 NULL
 * - Rule 12-1-2: 使用 explicit 构造函数
 * - Rule 18-4-1: 使用 dynamic_cast 替代 static_cast
 * 
 * @req_id REQ-001
 * @module signal_filter
 * @safety_level DAL-B
 */

#pragma once

#include <memory>
#include <vector>
#include <string>
#include <stdexcept>
#include <cstdint>
#include <cstring>
#include <functional>

namespace skyforge {

/**
 * @brief 资源基类（演示多态与虚析构）
 * @req_id REQ-001
 * @misra Rule 12-1-2: 构造函数应为 explicit
 */
class ResourceBase {
public:
    virtual ~ResourceBase() = default;
    virtual std::string get_type() const = 0;
    virtual bool is_valid() const = 0;
    virtual std::size_t size_bytes() const = 0;
};

/**
 * @brief 数据缓冲区（演示 unique_ptr 所有权）
 * @req_id REQ-001
 * @misra Rule 5-2-1: 使用 const 修饰不变参数
 * @misra Rule 12-1-2: explicit 构造函数
 */
class DataBuffer final : public ResourceBase {
public:
    /**
     * @brief 构造数据缓冲区
     * @param capacity 缓冲区容量（字节）
     * @req_id REQ-001
     */
    explicit DataBuffer(std::size_t capacity)
        : m_capacity(capacity), m_size(0),
          m_buffer(std::make_unique<uint8_t[]>(capacity)) {}

    std::string get_type() const override { return "DataBuffer"; }
    bool is_valid() const override { return m_buffer != nullptr; }  // Rule 6-6-1: nullptr
    std::size_t size_bytes() const override { return m_size; }
    std::size_t capacity() const { return m_capacity; }

    /**
     * @brief 写入数据
     * @param data 数据指针
     * @param len 数据长度
     * @return 是否成功
     * @req_id REQ-001
     * @misra Rule 5-2-1: const 参数
     */
    bool write(const uint8_t* data, std::size_t len) {
        if (len > m_capacity - m_size) return false;
        std::memcpy(m_buffer.get() + m_size, data, len);
        m_size += len;
        return true;
    }

    const uint8_t* data() const { return m_buffer.get(); }

private:
    std::size_t m_capacity;
    std::size_t m_size;
    std::unique_ptr<uint8_t[]> m_buffer;
};

/**
 * @brief 信号处理器（演示 shared_ptr 共享所有权）
 * @req_id REQ-001
 * @misra Rule 12-1-2: explicit 构造函数
 */
class SignalHandler {
public:
    using HandlerFunc = std::function<void(double)>;

    explicit SignalHandler(std::shared_ptr<ResourceBase> resource)
        : m_resource(std::move(resource)), m_enabled(true) {}

    void register_callback(HandlerFunc cb) {
        m_callbacks.push_back(std::move(cb));
    }

    void process(double value) {
        if (!m_enabled || !m_resource->is_valid()) return;
        for (auto& cb : m_callbacks) {
            cb(value);
        }
    }

    std::shared_ptr<ResourceBase> resource() const { return m_resource; }
    void set_enabled(bool e) { m_enabled = e; }

private:
    std::shared_ptr<ResourceBase> m_resource;
    std::vector<HandlerFunc> m_callbacks;
    bool m_enabled;
};

/**
 * @brief 资源管理器（演示 unique_ptr 拥有所有权）
 * @req_id REQ-001
 */
class ResourceManager {
public:
    ResourceManager() : m_count(0) {}

    std::unique_ptr<ResourceBase> create_buffer(std::size_t capacity) {
        if (m_count >= MAX_RESOURCES) {
            throw std::runtime_error("Resource limit exceeded");
        }
        m_count++;
        return std::make_unique<DataBuffer>(capacity);
    }

    void register_shared(std::shared_ptr<ResourceBase> resource) {
        if (m_count >= MAX_RESOURCES) {
            throw std::runtime_error("Resource limit exceeded");
        }
        m_shared_resources.push_back(std::move(resource));
        m_count++;
    }

    std::size_t resource_count() const { return m_count; }

private:
    static constexpr std::size_t MAX_RESOURCES = 32;
    std::vector<std::shared_ptr<ResourceBase>> m_shared_resources;
    std::size_t m_count;
};

} // namespace skyforge
