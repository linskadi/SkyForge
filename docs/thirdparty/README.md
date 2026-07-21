# SkyForge 外部工具离线包

本目录存放 SkyForge 运行所需的**外部工具离线安装包**，用于在无法连接公网或需要固定版本的生产/竞赛环境中快速部署依赖。

## 工具清单

| 工具 | 最低版本 | 用途 | 官方下载链接 |
|------|---------|------|-------------|
| CBMC | 6.0 | 形式化验证 | <https://github.com/diffblue/cbmc/releases> |
| Z3 | 4.12 | SMT 约束求解 | <https://github.com/Z3Prover/z3/releases> |
| Semgrep | 1.60 | 静态分析 | <https://github.com/semgrep/semgrep/releases> |
| GCC | 14.0 | 代码编译 | <https://gcc.gnu.org/releases.html> |
| LCOV | 2.0 | 覆盖率收集 | <https://github.com/linux-test-project/lcov/releases> |

> 提示：上述链接为官方发布页，请根据目标平台（Windows / Linux / macOS）下载对应版本的预编译二进制或安装包。

## 目录结构

建议按操作系统分类存放，便于 `tool_manager.py` 在启动时自动识别并添加到 `PATH`：

```text
thirdtool/
├── README.md
├── windows/
│   ├── cbmc/
│   │   └── cbmc.exe
│   ├── z3/
│   │   └── z3.exe
│   ├── semgrep/
│   │   └── semgrep.exe
│   ├── gcc/
│   │   └── bin/
│   │       └── gcc.exe
│   └── lcov/
│       └── bin/
│           └── lcov.exe
├── linux/
│   ├── cbmc/
│   ├── z3/
│   ├── semgrep/
│   ├── gcc/
│   └── lcov/
└── macos/
    ├── cbmc/
    ├── z3/
    ├── semgrep/
    ├── gcc/
    └── lcov/
```

## 安装方法

### 方式一：自动安装（推荐）

将解压后的工具二进制文件统一放入用户本地工具目录，SkyForge 启动时会自动将其加入 `PATH`：

- **Windows**: `%LOCALAPPDATA%\SkyForge\tools\bin`
- **Linux / macOS**: `~/.local/share/skyforge/tools/bin`

示例（PowerShell）：

```powershell
# 假设已下载并解压 CBMC
Copy-Item -Recurse -Path ".\cbmc-6.0\bin\*" -Destination "$env:LOCALAPPDATA\SkyForge\tools\bin"
```

示例（Bash）：

```bash
# 假设已下载并解压 Z3
mkdir -p ~/.local/share/skyforge/tools/bin
cp ./z3-4.12/bin/z3 ~/.local/share/skyforge/tools/bin/
chmod +x ~/.local/share/skyforge/tools/bin/z3
```

### 方式二：系统全局安装

如果环境允许，也可通过系统包管理器直接安装并确保版本满足要求：

- **Ubuntu/Debian**: `apt install gcc lcov`
- **macOS (Homebrew)**: `brew install cbmc z3 semgrep gcc lcov`
- **Windows (Chocolatey)**: `choco install gcc lcov`（部分工具需手动下载）

## 验证

安装完成后，在 SkyForge 项目根目录执行：

```bash
# 进入 Python 虚拟环境后
python -c "from app.core.tool_manager import check_all_tools; print(check_all_tools())"
```

或在 Studio 启动日志中观察各工具的检测结果。若某工具标记为 `found=False`，请参考上方清单检查是否已正确安装并加入 `PATH`。
