"""请求数据模型定义。"""

from pydantic import BaseModel
from typing import Optional


class GenerateRequest(BaseModel):
    """代码生成请求。"""

    requirement: str
    scade_file: Optional[str] = None


class UploadScadeRequest(BaseModel):
    """上传 SCADE 文件请求。"""

    filename: str
    content: str
