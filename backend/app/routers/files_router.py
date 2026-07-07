"""文件管理路由模块，提供文件下载和列表接口。"""

from fastapi import APIRouter, HTTPException
from app.utils.common_utils import get_current_files, get_work_dir

router = APIRouter()


@router.get("/api/files")
async def get_files(task_id: str):
    """获取任务工作目录下的文件列表。"""
    try:
        work_dir = get_work_dir(task_id)
        files = get_current_files(work_dir, "all")
        return {"files": files}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
