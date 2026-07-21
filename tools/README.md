## CBMC 安装

CBMC（C Bounded Model Checker）用于形式化验证阶段。本项目不内置 CBMC 安装包，请按以下方式安装：

- **Windows**: 从 https://www.cprover.org/cbmc/download/ 下载 `cbmc-<version>-win64.msi` 并安装
- **Linux (apt)**: `sudo apt install cbmc`
- **macOS (brew)**: `brew install cbmc`

安装后确保 `cbmc` 命令在 PATH 中可用。运行 `cbmc --version` 验证安装。
