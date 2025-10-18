"""
通用模型定义
"""
from typing import TypeVar, Generic, Optional, Any, List, Dict
from pydantic import BaseModel, Field

T = TypeVar('T')

# 状态码定义
class StatusCode:
    """状态码定义"""
    SUCCESS = 200  # 成功
    
    # 参数错误 (4xx)
    PARAM_ERROR = 400  # 参数错误
    UNAUTHORIZED = 401  # 未授权
    FORBIDDEN = 403  # 禁止访问
    NOT_FOUND = 404  # 资源不存在
    METHOD_NOT_ALLOWED = 405  # 方法不允许
    CONFLICT = 409  # 资源冲突
    OPERATION_FAILED = 422  # 操作失败
    
    # 服务端错误 (5xx)
    SERVER_ERROR = 500  # 服务器内部错误
    NOT_IMPLEMENTED = 501  # 未实现
    SERVICE_UNAVAILABLE = 503  # 服务不可用
    TIMEOUT = 504  # 超时

class CommonResponse(BaseModel, Generic[T]):
    """通用响应模型"""
    code: int = Field(default=StatusCode.SUCCESS, description="状态码，200表示成功，4xx表示参数错误，5xx表示服务端错误")
    message: str = Field(default="操作成功", description="提示信息")
    data: Optional[T] = Field(default=None, description="返回数据")

class PageResult(BaseModel, Generic[T]):
    """分页结果模型"""
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页大小")
    data: List[T] = Field(default=[], description="分页数据")

# 健康检查响应模型
class HealthResponse(BaseModel):
    status: str
    version: str 