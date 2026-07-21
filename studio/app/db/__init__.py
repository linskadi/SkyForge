"""数据库初始化模块。

使用 SQLite + SQLAlchemy 2.0，零配置，单文件 studio/data/skyforge.db。
"""
import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 数据库文件路径（相对 main.py 工作目录，运行目录为 SkyForge/）
_DB_DIR = os.path.join("studio", "data")
_DB_PATH = os.path.join(_DB_DIR, "skyforge.db")

# 启动时确保目录存在
os.makedirs(_DB_DIR, exist_ok=True)

engine: Engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


# 启用 SQLite 外键约束
@event.listens_for(engine, "connect")
def _enable_fk(dbapi_conn, _conn_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类。"""

    pass


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每个请求一个 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
