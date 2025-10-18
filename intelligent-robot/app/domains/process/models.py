"""
流程相关模型
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from app.db.connection import Base
from app.domains.common_models import CommonResponse

class Process(Base):
    """流程模型"""
    
    __tablename__ = "process"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="流程名称")
    version = Column(String(10), nullable=True, comment="版本号(V 1.0.0)")
    content = Column(Text, nullable=True, comment="流程内容")
    local_filename = Column(String(255), nullable=True, comment="本地文件名")
    created_at = Column(String, comment="创建时间")
    is_deleted = Column(String(1), default='0', comment="是否删除(0:存在 1:删除)")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        """
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "content": self.content,
            "local_filename": self.local_filename,
            "created_at": self.created_at,
            "is_deleted": self.is_deleted
        }

class ProcessInstance(Base):
    """流程实例模型"""

    __tablename__ = "process_instance"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    process_id = Column(Integer, nullable=False, comment="流程ID")
    status = Column(String(2), default='-1', nullable=True, comment="运行状态(-1:等待中 0:运行中 1:已完成 2:暂停中)")
    result = Column(String(2), default='-1', nullable=True, comment="运行结果(-1:无结果 0:失败 1:成功)")
    start_time = Column(String, nullable=True, comment="开始时间")
    end_time = Column(String, nullable=True, comment="结束时间")
    duration = Column(Integer, nullable=True, comment="运行时长（秒）")
    log = Column(Text, nullable=True, comment="日志")
    log_path = Column(String(255), default=None, comment='日志路径')
    is_deleted = Column(String(1), default='0', comment="是否删除(0:存在 1:删除)")

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        """
        return {
            "id": self.id,
            "process_id": self.process_id,
            "status": self.status,
            "result": self.result,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "log": self.log,
            "log_path": self.log_path,
            "is_deleted": self.is_deleted
        }

# 流程列表项模型
class ProcessListItem(BaseModel):
    """流程列表项模型"""
    id: int
    name: str
    version: str
    create_time: str
    update_time: str
    run_count: int = 0
    pause_count: int = 0

# 流程列表响应模型
class ProcessListResponse(BaseModel):
    """流程列表响应模型"""
    total: int
    page_num: int
    page_size: int
    data: List[ProcessListItem]

# 流程ID和名称项模型
class ProcessIdNameItem(BaseModel):
    """流程ID和名称项模型"""
    id: int
    name: str

# 流程ID和名称列表响应模型
class ProcessIdNameListResponse(BaseModel):
    """流程ID和名称列表响应模型"""
    total: int
    data: List[ProcessIdNameItem]

# Pydantic请求模型，用于API请求
class ProcessImportRequest(BaseModel):
    process_id: Optional[int] = None
    name: str

# Pydantic响应模型，用于API返回
class ProcessData(BaseModel):
    process_id: Optional[int] = None

class InstanceData(BaseModel):
    instance_id: Optional[int] = None

# 使用通用响应模型
class ProcessImportResponse(CommonResponse[ProcessData]):
    pass

class ProcessStartResponse(CommonResponse[InstanceData]):
    pass

class ProcessDeleteResponse(CommonResponse):
    pass

class ProcessStopResponse(CommonResponse[InstanceData]):
    pass

