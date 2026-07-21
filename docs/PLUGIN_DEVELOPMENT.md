# SkyForge Plugin Development Guide

## Overview

This guide explains how to develop plugins for the SkyForge plugin system. Plugins allow you to extend SkyForge's functionality by adding custom agents, tools, templates, reports, and validators.

## Table of Contents

1. [Plugin Architecture](#plugin-architecture)
2. [Coding Standards Plugin (Implemented)](#coding-standards-plugin-implemented)
3. [Getting Started](#getting-started)
4. [Plugin Types](#plugin-types)
5. [Plugin Lifecycle](#plugin-lifecycle)
6. [Plugin Metadata](#plugin-metadata)
7. [Plugin Configuration](#plugin-configuration)
8. [Plugin Dependencies](#plugin-dependencies)
9. [Plugin Events](#plugin-events)
10. [Examples](#examples)
11. [Best Practices](#best-practices)

## Plugin Architecture

The SkyForge plugin system consists of the following components:

- **PluginBase**: Abstract base class for all plugins
- **PluginLoader**: Discovers and loads plugins from the file system
- **PluginRegistry**: Manages plugin metadata and dependencies
- **PluginManager**: Central manager for plugin lifecycle

### Directory Structure

```
plugins/
├── __init__.py
├── base.py              # Plugin base classes
├── loader.py            # Plugin loader
├── manager.py           # Plugin manager
├── registry.py          # Plugin registry
└── examples/            # Example plugins
    ├── agent_plugin/
    ├── tool_plugin/
    ├── template_plugin/
    ├── report_plugin/
    └── validator_plugin/
```

## Coding Standards Plugin (Implemented)

SkyForge 已实现可插拔编码标准系统，位于 `src/skyforge_engine/coding_standards/`。DO-178C 过程标准固定，编码标准通过 `CodingStandardRegistry` 动态注册。

### 核心组件

- **base.py**: 包含 `CodingStandard` 数据类和 `get_registry()` 函数（全局单例注册表）
- **CodingStandardRegistry**: 统一管理编码标准的注册、查询、迭代，支持按语言、标准ID、规则ID多维查询

### 已注册标准

| 标准 ID | 名称 | 语言 | 红线规则 | 修复器 | Mock 违规 |
|---------|------|------|---------|--------|-----------|
| `misra_c_2012` | MISRA-C:2012 | C | 10 条 | 57 个 | 8 种 |
| `jsf_av_cpp` | MISRA-C++/JSF AV C++/CERT C++ | C++ | 5 条 | — | 4 种 |
| `python_safety` | 军工软件Python编程规范 (T/ZASDI 0002-2023) | Python | 3 条 | 4 个 | 4 种 |

### 添加新编码标准

```python
from skyforge_engine.coding_standards.base import CodingStandard, get_registry

# 1. 定义编码标准
my_std = CodingStandard(
    standard_id="my_custom_standard",
    name="My Custom Standard",
    languages=["c"],
    version="1.0",
    rule_data_file="path/to/rules.txt",
    red_line_rules=["R1", "R2"],
    fixers={"R1": my_fixer_func},
    mock_scan_patterns=[{"pattern": r"...", "rule_id": "R1", "severity": "error", "message": "..."}],
    rule_prefix_category={"R": "Category 1"},
    agent_default_queries={"code_generator": ["query1", "query2"]},
    agent_display_names={"code_generator": "代码生成 Agent"},
    priority=100,
)

# 2. 注册到全局 Registry
registry = get_registry()
registry.register(my_std)

# 3. 使用
rules = registry.get_red_line_rules("c")
std = registry.get("my_custom_standard")
fixers = registry.get_fixers("c")
```

### 集成点

编码标准注册后自动被以下模块使用：
- `rag_enhancer.py`: 红线规则检测、Agent 查询
- `rule_parser.py`: 规则分类映射
- `cppcheck_scanner.py`: Mock 扫描模式
- `code_repairer.py`: 代码修复函数调度

---

## Getting Started

### 1. Create a Plugin Directory

Create a new directory for your plugin:

```bash
mkdir my_plugin
cd my_plugin
```

### 2. Create Plugin File

Create a Python file with your plugin implementation:

```python
# my_plugin.py
from typing import Any, Dict, List
from skyforge_engine.plugins.base import PluginBase, PluginMetadata

class MyPlugin(PluginBase):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            author="Your Name",
            description="My awesome plugin",
            plugin_type="tool",  # or agent, template, report, validator
            dependencies={},
            conflicts=[],
            min_engine_version="1.0.0"
        )
    
    def on_load(self, config: Dict[str, Any]) -> None:
        super().on_load(config)
        # Initialize your plugin
    
    def on_activate(self) -> None:
        super().on_activate()
        # Start your plugin services
```

### 3. Register Your Plugin

Add your plugin to the plugin directory configuration:

```python
from skyforge_engine.plugins import PluginManager

manager = PluginManager()
manager.add_plugin_dir("/path/to/your/plugin")
manager.load_all_plugins()
manager.activate_all_plugins()
```

## Plugin Types

### AgentPlugin

Custom intelligent agents that perform specific tasks:

```python
from skyforge_engine.plugins.base import AgentPlugin, PluginMetadata

class MyAgentPlugin(AgentPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_agent",
            version="1.0.0",
            author="Your Name",
            description="My custom agent",
            plugin_type="agent"
        )
    
    def create_agent(self, config: Dict[str, Any]) -> Any:
        # Create and return your agent instance
        return MyAgent(config)
    
    def get_capabilities(self) -> List[str]:
        return ["capability1", "capability2"]
```

### ToolPlugin

Custom tools that can be used by agents:

```python
from skyforge_engine.plugins.base import ToolPlugin, PluginMetadata

class MyToolPlugin(ToolPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_tool",
            version="1.0.0",
            author="Your Name",
            description="My custom tool",
            plugin_type="tool"
        )
    
    def execute(self, **kwargs) -> Any:
        # Implement your tool logic
        return {"result": "success"}
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }
```

### TemplatePlugin

Custom code templates:

```python
from skyforge_engine.plugins.base import TemplatePlugin, PluginMetadata

class MyTemplatePlugin(TemplatePlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_template",
            version="1.0.0",
            author="Your Name",
            description="My custom template",
            plugin_type="template"
        )
    
    def render(self, context: Dict[str, Any]) -> str:
        # Render your template
        return f"Hello, {context.get('name', 'World')}!"
    
    def get_template_names(self) -> List[str]:
        return ["template1", "template2"]
```

### ReportPlugin

Custom report generators:

```python
from skyforge_engine.plugins.base import ReportPlugin, PluginMetadata

class MyReportPlugin(ReportPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_report",
            version="1.0.0",
            author="Your Name",
            description="My custom report",
            plugin_type="report"
        )
    
    def generate(self, data: Dict[str, Any], options: Dict[str, Any]) -> Union[str, bytes]:
        # Generate your report
        return f"<html><body>{data}</body></html>"
    
    def get_supported_formats(self) -> List[str]:
        return ["html", "pdf"]
```

### ValidatorPlugin

Custom validation rules:

```python
from skyforge_engine.plugins.base import ValidatorPlugin, PluginMetadata

class MyValidatorPlugin(ValidatorPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_validator",
            version="1.0.0",
            author="Your Name",
            description="My custom validator",
            plugin_type="validator"
        )
    
    def validate(self, data: Any, rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        errors = []
        # Validate data against rules
        if not data:
            errors.append({"rule": "required", "message": "Data is required"})
        return errors
    
    def get_validation_rules(self) -> List[str]:
        return ["rule1", "rule2"]
```

## Plugin Lifecycle

Plugins go through the following lifecycle states:

1. **UNLOADED**: Initial state
2. **LOADED**: Plugin file loaded, `on_load()` called
3. **ACTIVE**: Plugin activated, `on_activate()` called
4. **INACTIVE**: Plugin deactivated, `on_deactivate()` called
5. **ERROR**: Plugin encountered an error

### Lifecycle Methods

```python
class MyPlugin(PluginBase):
    def on_load(self, config: Dict[str, Any]) -> None:
        """Called when plugin is loaded."""
        super().on_load(config)
        # Initialize resources
    
    def on_activate(self) -> None:
        """Called when plugin is activated."""
        super().on_activate()
        # Start services
    
    def on_deactivate(self) -> None:
        """Called when plugin is deactivated."""
        super().on_deactivate()
        # Stop services
    
    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        super().on_unload()
        # Clean up resources
    
    def on_error(self, error: Exception) -> None:
        """Called when an error occurs."""
        super().on_error(error)
        # Handle error
```

## Plugin Metadata

Every plugin must provide metadata:

```python
PluginMetadata(
    name="unique_plugin_id",           # Required
    version="1.0.0",                    # Required (semver)
    author="Your Name",                 # Required
    description="Plugin description",   # Required
    plugin_type="tool",                 # Required
    dependencies={"other_plugin": ">=1.0.0"},  # Optional
    conflicts=["conflicting_plugin"],    # Optional
    min_engine_version="1.0.0",         # Optional
    max_engine_version="2.0.0",         # Optional
    tags=["tag1", "tag2"],              # Optional
    homepage="https://example.com",     # Optional
    repository="https://github.com/...",  # Optional
    license="MIT"                       # Optional
)
```

## Plugin Configuration

Plugins can access configuration through the config parameter:

```python
def on_load(self, config: Dict[str, Any]) -> None:
    super().on_load(config)
    
    # Access configuration
    api_key = config.get("api_key")
    debug_mode = config.get("debug", False)
    
    # Set default values
    self.timeout = config.get("timeout", 30)
```

Configuration can be set in the plugin manager:

```python
manager = PluginManager()
manager.set_config({
    "plugins": {
        "my_plugin": {
            "api_key": "secret_key",
            "timeout": 60
        }
    }
})
manager.load_all_plugins()
```

## Plugin Dependencies

Plugins can declare dependencies on other plugins:

```python
PluginMetadata(
    name="my_plugin",
    dependencies={
        "required_plugin": ">=1.0.0",
        "another_plugin": ">=2.0.0,<3.0.0"
    }
)
```

### Using Required Plugins

```python
def on_activate(self) -> None:
    super().on_activate()
    
    # Require another plugin
    other_plugin = self.require_plugin("other_plugin", min_version="1.0.0")
    
    # Use the required plugin
    result = other_plugin.do_something()
```

## Plugin Events

Plugins can listen to system events:

```python
from skyforge_engine.plugins.base import PluginEvent

def on_activate(self) -> None:
    super().on_activate()
    
    # Add event handler
    self._plugin_manager.add_event_handler(
        PluginEvent.PLUGIN_ACTIVATED,
        self._on_plugin_activated
    )

def _on_plugin_activated(self, event: PluginEvent, data: Dict[str, Any]) -> None:
    """Handle plugin activated event."""
    plugin_name = data.get("plugin_name")
    print(f"Plugin activated: {plugin_name}")
```

### Available Events

- `PLUGIN_LOADED`: Plugin file loaded
- `PLUGIN_ACTIVATED`: Plugin activated
- `PLUGIN_DEACTIVATED`: Plugin deactivated
- `PLUGIN_UNLOADED`: Plugin unloaded
- `PLUGIN_ERROR`: Plugin error occurred
- `PLUGIN_DEPENDENCY_MISSING`: Required plugin missing
- `PLUGIN_VERSION_CONFLICT`: Version conflict detected

## Examples

See the `examples/` directory for complete plugin examples:

- `agent_plugin/`: Security analysis agent
- `tool_plugin/`: Code formatting tools
- `template_plugin/`: REST API templates
- `report_plugin/`: HTML report generator
- `validator_plugin/`: Data validation rules

## Best Practices

### 1. Keep Plugins Focused

Each plugin should do one thing well. Don't create monolithic plugins.

### 2. Handle Errors Gracefully

Always implement proper error handling:

```python
def on_load(self, config: Dict[str, Any]) -> None:
    try:
        super().on_load(config)
        # Initialize plugin
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
```

### 3. Use Configuration

Make your plugins configurable:

```python
def on_load(self, config: Dict[str, Any]) -> None:
    super().on_load(config)
    
    self.api_url = config.get("api_url", "https://api.example.com")
    self.timeout = config.get("timeout", 30)
    self.debug = config.get("debug", False)
```

### 4. Document Your Plugins

Provide clear documentation:

```python
class MyPlugin(PluginBase):
    """
    My awesome plugin.
    
    This plugin provides X functionality.
    
    Configuration:
        - api_url: API endpoint URL
        - timeout: Request timeout in seconds
        - debug: Enable debug mode
    
    Example:
        ```python
        plugin = MyPlugin()
        plugin.on_load({"api_url": "https://api.example.com"})
        plugin.on_activate()
        ```
    """
```

### 5. Test Your Plugins

Write tests for your plugins:

```python
import pytest
from my_plugin import MyPlugin

def test_plugin_metadata():
    plugin = MyPlugin()
    metadata = plugin.get_metadata()
    
    assert metadata.name == "my_plugin"
    assert metadata.version == "1.0.0"
    assert metadata.plugin_type == "tool"

def test_plugin_lifecycle():
    plugin = MyPlugin()
    
    # Test load
    plugin.on_load({})
    assert plugin.state == PluginState.LOADED
    
    # Test activate
    plugin.on_activate()
    assert plugin.state == PluginState.ACTIVE
    
    # Test deactivate
    plugin.on_deactivate()
    assert plugin.state == PluginState.INACTIVE
    
    # Test unload
    plugin.on_unload()
    assert plugin.state == PluginState.UNLOADED
```

### 6. Follow Versioning

Use semantic versioning:

- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes (backward compatible)

### 7. Minimize Dependencies

Keep dependencies minimal to reduce conflicts:

```python
# Good
dependencies={
    "core_plugin": ">=1.0.0"
}

# Avoid
dependencies={
    "plugin_a": ">=1.0.0",
    "plugin_b": ">=1.0.0",
    "plugin_c": ">=1.0.0",
    # ... many more
}
```

### 8. Use Logging

Implement proper logging:

```python
import logging

logger = logging.getLogger(__name__)

class MyPlugin(PluginBase):
    def on_load(self, config: Dict[str, Any]) -> None:
        logger.info("Loading my plugin")
        super().on_load(config)
        
        if config.get("debug"):
            logger.debug("Debug mode enabled")
```

## Troubleshooting

### Plugin Not Loading

1. Check file path and permissions
2. Verify plugin class inherits from correct base class
3. Ensure `get_metadata()` returns valid metadata
4. Check for import errors

### Plugin Not Activating

1. Verify all dependencies are available
2. Check for version conflicts
3. Review plugin logs for errors
4. Ensure no conflicting plugins are active

### Performance Issues

1. Profile your plugin code
2. Avoid heavy operations in lifecycle methods
3. Use caching where appropriate
4. Consider lazy loading of resources

## Support

For issues or questions:

- Check the [GitHub Issues](https://github.com/skyforge/skyforge/issues)
- Review existing plugins for examples
- Read the API documentation

## License

Plugin development follows the same license as SkyForge (MIT).
