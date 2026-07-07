"""通用工具函数模块，提供任务 ID 生成、文件操作等功能。"""

import os
import datetime
import hashlib
from app.utils.log_util import logger
import re

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def create_task_id() -> str:
    """生成基于时间戳和随机哈希的唯一任务 ID。"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    random_hash = hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()[:8]
    return f"{timestamp}-{random_hash}"


def ensure_safe_task_id(task_id: str) -> str:
    """验证任务 ID 的合法性，防止路径遍历攻击。

    Args:
        task_id: 待验证的任务 ID。

    Returns:
        验证通过的任务 ID。

    Raises:
        ValueError: 任务 ID 不合法时抛出。
    """
    normalized = (task_id or "").strip()
    if not normalized or not TASK_ID_PATTERN.fullmatch(normalized):
        raise ValueError("非法 task_id")
    return normalized


def create_work_dir(task_id: str) -> str:
    """为指定任务创建工作目录。

    Args:
        task_id: 任务 ID。

    Returns:
        工作目录路径。
    """
    work_dir = os.path.join("project", "work_dir", task_id)

    try:
        os.makedirs(work_dir, exist_ok=True)
        return work_dir
    except Exception as e:
        logger.error(f"创建工作目录失败: {str(e)}")
        raise


def get_work_dir(task_id: str) -> str:
    """获取指定任务的工作目录路径。

    Args:
        task_id: 任务 ID。

    Returns:
        工作目录路径。

    Raises:
        FileNotFoundError: 工作目录不存在时抛出。
    """
    work_dir = os.path.join("project", "work_dir", task_id)
    if os.path.exists(work_dir):
        return work_dir
    else:
        logger.error(f"工作目录不存在: {work_dir}")
        raise FileNotFoundError(f"工作目录不存在: {work_dir}")


def get_current_files(folder_path: str, type: str = "all") -> list[str]:
    """获取指定目录下的文件列表。

    Args:
        folder_path: 目录路径。
        type: 文件类型过滤（all/md/data/image）。
    """
    files = os.listdir(folder_path)
    if type == "all":
        return files
    elif type == "md":
        return [file for file in files if file.endswith(".md")]
    elif type == "data":
        return [
            file for file in files if file.endswith(".xlsx") or file.endswith(".csv")
        ]
    elif type == "image":
        return [
            file for file in files if file.endswith(".png") or file.endswith(".jpg")
        ]
    return []
