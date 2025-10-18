from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from typing import Dict, Any, Optional

from app.domains.process.models import (
    ProcessImportResponse, ProcessStartResponse, ProcessDeleteResponse, 
    ProcessImportRequest, ProcessData, InstanceData, ProcessListResponse,
    ProcessStopResponse, ProcessIdNameListResponse
)
from app.domains.common_models import CommonResponse, PageResult, StatusCode
from app.services.process_service import ProcessService
from app.db.connection import get_db

# 创建路由器
router = APIRouter(
    prefix="/process",
    tags=["流程管理"],
    responses={404: {"description": "Not found"}},
)

# 1. 流程列表 API
@router.get("/list", response_model=CommonResponse[ProcessListResponse])
async def get_processes(
    page_num: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=100),
    name: Optional[str] = None,
    db = Depends(get_db)
):
    """
    获取流程列表，支持分页、按名称搜索和过滤已删除流程
    
    参数:
    - page_num: 页码，默认为1
    - page_size: 每页记录数，默认为6
    - name: 流程名称关键字，用于模糊搜索
    
    返回:
    - 流程列表，包含最新版本的流程，按更新时间降序排序
    - 总记录数
    """
    return ProcessService.get_processes(page_num, page_size, name, db)

# 获取所有流程ID和名称列表 API
@router.get("/id-names", response_model=CommonResponse[ProcessIdNameListResponse])
async def get_all_process_id_names(
    name: Optional[str] = None,
    db = Depends(get_db)
):
    """
    获取所有流程的ID和名称列表，支持名称模糊搜索
    
    参数:
    - name: 流程名称关键字，用于模糊搜索
    
    返回:
    - 流程ID和名称列表，按名称升序排序
    - 总记录数
    """
    return ProcessService.get_all_process_id_names(name, db)

# 2. 导入流程 API
@router.post("/import", response_model=ProcessImportResponse)
async def import_process(
    file: UploadFile = File(...),
    name: str = Form(...),
    process_id: Optional[int] = Form(None),
    db = Depends(get_db)
):
    """
    导入流程文件
    
    参数:
    - file: 上传的流程文件，后缀必须是.robot
    - name: 流程名称（仅在创建新流程时使用，更新流程时会保持原名称）
    - process_id: 流程ID（可选，如果提供则更新版本）
    
    规则:
    1. 文件后缀必须是.robot
    2. 如果未提供process_id，则创建新流程，名称不能重复，初始版本为V 1.0.0
    3. 如果提供process_id，则版本号加1，且保持原来的流程名称不变
    4. 文件将保存到script目录，命名为: 名称_yyyymmddhhMMss_版本号.robot
    5. 更新流程时，同名的旧版本会被标记为删除状态，只保留最新版本
    """
    if not file.filename.endswith('.robot'):
        return CommonResponse[ProcessData](
            code=StatusCode.PARAM_ERROR,
            message="文件后缀必须是.robot",
            data=None
        )
    
    result = ProcessService.import_process(file, name, process_id, db)
    
    if result["code"] != StatusCode.SUCCESS:
        return CommonResponse[ProcessData](
            code=result["code"],
            message=result["message"],
            data=None
        )
    
    return CommonResponse[ProcessData](
        code=StatusCode.SUCCESS,
        message=result["message"],
        data=ProcessData(process_id=result["data"]["process_id"])
    )

# 3. 启动流程 API
@router.post("/{process_id}/start", response_model=ProcessStartResponse)
async def start_process(process_id: int, db = Depends(get_db)):
    """
    启动指定流程，创建新的实例
    """
    result = ProcessService.start_process(process_id, db)
    
    if result["code"] != StatusCode.SUCCESS:
        return CommonResponse[InstanceData](
            code=result["code"],
            message=result["message"],
            data=None
        )
    
    return CommonResponse[InstanceData](
        code=StatusCode.SUCCESS,
        message=result["message"],
        data=InstanceData(instance_id=result["data"]["instance_id"])
    )

# 4. 删除流程 API
@router.delete("/{process_id}", response_model=ProcessDeleteResponse)
async def delete_process(process_id: int, db = Depends(get_db)):
    """
    删除指定流程及其所有实例（逻辑删除）
    
    规则:
    1. 流程必须存在且未被删除
    2. 流程的所有实例必须全部为已完成状态（状态为1）
    3. 使用事务同时删除流程及其所有实例
    
    返回:
    - 删除结果
    """
    result = ProcessService.delete_process(process_id, db)
    
    return CommonResponse(
        code=result["code"],
        message=result["message"],
        data=result.get("data")
    )

# 5. 实例列表 API
@router.get("/instances", response_model=CommonResponse[Dict[str, Any]])
async def get_instances(
    page_num: int = Query(1, ge=1),
    page_size: int = Query(6, ge=1, le=100),
    process_id: Optional[int] = None,
    status: Optional[str] = None,
    db = Depends(get_db)
):
    """
    获取流程实例列表，支持分页和按流程ID过滤
    """
    return ProcessService.get_instances(page_num, page_size, process_id, status, db)

# 6. 停止流程实例 API
@router.post("/instances/{instance_id}/stop", response_model=ProcessStopResponse)
async def stop_instance(instance_id: int, db = Depends(get_db)):
    """
    停止指定的流程实例
    
    参数:
    - instance_id: 流程实例ID
    
    返回:
    - 停止结果
    """
    result = ProcessService.stop_instance(instance_id, db)
    
    if result["code"] != StatusCode.SUCCESS:
        return CommonResponse[InstanceData](
            code=result["code"],
            message=result["message"],
            data=None
        )
    
    return CommonResponse[InstanceData](
        code=StatusCode.SUCCESS,
        message=result["message"],
        data=InstanceData(instance_id=result["data"]["instance_id"])
    ) 