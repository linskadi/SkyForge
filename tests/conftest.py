# -*- coding: utf-8 -*-
"""pytest 配置：将 src/ 加入 sys.path，使 skyforge_engine 包可被导入。

运行方式:
    cd SkyForge
    .venv\\Scripts\\python.exe -m pytest tests/test_arinc653_adapter.py -v
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
