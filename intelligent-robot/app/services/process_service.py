import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import Depends, UploadFile
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.domains.common_models import StatusCode
from app.domains.process.models import Process
from app.mapper.process.mappers import ProcessMapper, ProcessInstanceMapper
from app.robot.job_loader import load_pending_jobs
from app.robot.job_worker import stop_job

# 创建映射器实例
process_mapper = ProcessMapper()
instance_mapper = ProcessInstanceMapper()


class ProcessService:
    @staticmethod
    def get_processes(
            page_num: int = 1,
            page_size: int = 6,
            name: Optional[str] = None,
            db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """获取流程列表"""
        result = process_mapper.get_latest_processes(
            db=db,
            page=page_num,
            page_size=page_size,
            search_keyword=name
        )

        # 转换为通用响应格式
        return {
            "code": StatusCode.SUCCESS,
            "message": "获取流程列表成功",
            "data": result
        }
        
    @staticmethod
    def get_all_process_id_names(
            name: Optional[str] = None,
            db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """获取所有流程的ID和名称列表，支持名称模糊搜索"""
        result = process_mapper.get_all_process_id_names(
            db=db,
            search_keyword=name
        )

        # 转换为通用响应格式
        return {
            "code": StatusCode.SUCCESS,
            "message": "获取流程ID和名称列表成功",
            "data": result
        }

    @staticmethod
    def import_process(
            file: UploadFile,
            name: str,
            process_id: Optional[int] = None,
            db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """导入流程
        
        Args:
            file: 上传的文件
            name: 流程名称
            process_id: 流程ID（可选，如果提供则更新版本）
            db: 数据库会话
            
        Returns:
            Dict[str, Any]: 导入结果
        """
        try:
            # 1. 验证文件后缀必须是.robot
            if not file.filename.endswith('.robot'):
                return {
                    "code": StatusCode.PARAM_ERROR,
                    "message": "文件后缀必须是.robot",
                    "data": None
                }

            # 2. 检查流程名称是否重复（仅在创建新流程时检查）
            if process_id is None:
                # 使用 get_multi 方法查询同名流程
                existing_processes = process_mapper.get_multi(
                    db=db,
                    filters={"name": name}  # BaseMapper 会自动添加 is_deleted='0' 过滤条件
                )

                if existing_processes:
                    return {
                        "code": StatusCode.CONFLICT,
                        "message": f"流程名称 '{name}' 已存在",
                        "data": None
                    }

                # 新流程的初始版本
                version = "V 1.0.0"
                process_name = name  # 新建流程时使用传入的名称
            else:
                # 获取现有流程
                existing_process = process_mapper.get(db, process_id)
                if not existing_process:
                    return {
                        "code": StatusCode.NOT_FOUND,
                        "message": f"流程不存在: ID {process_id}",
                        "data": None
                    }

                # 更新流程时保持原来的名称不变
                process_name = existing_process.name

                # 获取相同名称的最新版本流程
                # 使用 get_multi 方法查询同名流程
                latest_processes = process_mapper.get_multi(
                    db=db,
                    filters={"name": process_name}  # BaseMapper 会自动添加 is_deleted='0' 过滤条件
                )

                if not latest_processes:
                    # 如果没有找到最新版本（可能所有流程都被删除了），使用初始版本
                    version = "V 1.0.0"
                else:
                    # 找出创建时间最新的流程
                    latest_process = max(latest_processes, key=lambda p: p.created_at)

                    # 解析最新版本号并增加
                    try:
                        version_parts = latest_process.version.split()
                        if len(version_parts) == 2:
                            version_nums = version_parts[1].split('.')
                            if len(version_nums) == 3:
                                # 版本号加1
                                new_version_num = int(version_nums[2]) + 1
                                if new_version_num >= 10:  # 十进制，10进1
                                    new_version_num = 0
                                    middle_num = int(version_nums[1]) + 1
                                    if middle_num >= 10:
                                        middle_num = 0
                                        major_num = int(version_nums[0]) + 1
                                    else:
                                        major_num = int(version_nums[0])
                                else:
                                    middle_num = int(version_nums[1])
                                    major_num = int(version_nums[0])

                                version = f"V {major_num}.{middle_num}.{new_version_num}"
                            else:
                                version = "V 1.0.0"  # 版本格式错误，重置
                        else:
                            version = "V 1.0.0"  # 版本格式错误，重置
                    except Exception:
                        version = "V 1.0.0"  # 解析错误，重置版本

            # 3. 读取文件内容
            content = file.file.read()

            # 4. 确保script目录存在
            script_dir = os.path.join(os.getcwd(), "script")
            if not os.path.exists(script_dir):
                os.makedirs(script_dir)

            # 5. 生成本地文件名: 名称_yyyymmddhhMMss_版本号.robot
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            local_filename = f"{process_name}_{timestamp}_{version.replace(' ', '_')}.robot"
            file_path = os.path.join(script_dir, local_filename)

            # 6. 保存文件到本地
            with open(file_path, "wb") as f:
                f.write(content)

            # 7. 创建新的流程记录
            new_process = {
                "name": process_name,  # 使用确定的流程名称
                "version": version,
                "content": content.decode('utf-8'),
                "local_filename": local_filename,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 手动设置创建时间
                # 不需要指定 is_deleted，BaseMapper 会自动设置为 '0'
            }

            # 8. 保存到数据库
            process = process_mapper.create(db, new_process)

            # 9. 将同名的旧版本标记为删除状态
            if process_id is not None:
                # 查询所有同名的旧版本（除了刚创建的新版本）
                old_versions = db.query(Process).filter(
                    Process.name == process_name,
                    Process.id != process.id,
                    Process.is_deleted == '0'  # 只处理未删除的记录
                ).all()

                # 将旧版本标记为删除状态
                for old_version in old_versions:
                    old_version.is_deleted = '1'  # 1表示已删除

                # 提交更改
                db.commit()

            return {
                "code": StatusCode.SUCCESS,
                "message": "流程导入成功",
                "data": {"process_id": process.id}
            }
        except Exception as e:
            # 发生错误时，删除已创建的文件
            try:
                if 'file_path' in locals() and os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass

            return {
                "code": StatusCode.SERVER_ERROR,
                "message": f"流程导入失败: {str(e)}",
                "data": None
            }

    @staticmethod
    def start_process(process_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
        """启动流程实例"""
        # 检查流程是否存在
        process = process_mapper.get(db, process_id)
        if not process:
            return {
                "code": StatusCode.NOT_FOUND,
                "message": f"流程不存在: ID {process_id}",
                "data": None
            }

        # 创建新实例，设置流程ID和初始状态
        new_instance = {
            "process_id": process_id,
            "status": "-1",  # 等待中
            "result": "-1",  # 无结果
        }

        instance = instance_mapper.create(db, new_instance)

        # 异步加载待执行任务
        async def async_load_job():
            # 自动将新任务添加到队列
            await load_pending_jobs()

        # 创建异步任务但不等待它完成
        asyncio.create_task(async_load_job())

        return {
            "code": StatusCode.SUCCESS,
            "message": "流程实例启动成功",
            "data": {"instance_id": instance.id}
        }

    @staticmethod
    def delete_process(process_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
        """删除流程（软删除）
        
        执行以下操作：
        1. 检查流程是否存在
        2. 检查流程的所有实例是否全部为已完成状态（状态为1）
        3. 使用事务同时逻辑删除流程及其所有实例
        
        Args:
            process_id: 流程ID
            db: 数据库会话
            
        Returns:
            Dict[str, Any]: 删除结果
        """
        try:
            # 1. 检查流程是否存在
            process = process_mapper.get(db, process_id)
            if not process:
                return {
                    "code": StatusCode.NOT_FOUND,
                    "message": f"流程不存在: ID {process_id}",
                    "data": None
                }
            
            # 2. 检查流程的所有实例是否全部为已完成状态（状态为1）
            # 直接统计未完成实例的数量
            unfinished_count = instance_mapper.count_unfinished_instances(db, process_id)
            
            # 如果有未完成的实例，则不允许删除
            if unfinished_count > 0:
                return {
                    "code": StatusCode.OPERATION_FAILED,
                    "message": f"流程存在 {unfinished_count} 个未完成的实例，无法删除",
                    "data": None
                }
            
            # 3. 使用事务同时逻辑删除流程及其所有实例
            # 获取所有未删除的实例
            instances = instance_mapper.get_multi(
                db=db,
                filters={"process_id": process_id}  # BaseMapper 会自动添加 is_deleted='0' 过滤条件
            )
            
            # 开始事务
            try:
                # 3.1 逻辑删除流程
                process.is_deleted = '1'  # 1表示已删除
                db.add(process)
                
                # 3.2 逻辑删除所有实例
                for instance in instances:
                    instance.is_deleted = '1'  # 1表示已删除
                    db.add(instance)
                
                # 提交事务
                db.commit()
                
                return {
                    "code": StatusCode.SUCCESS,
                    "message": f"流程删除成功，同时删除了 {len(instances)} 个相关实例",
                    "data": None
                }
            except Exception as e:
                # 回滚事务
                db.rollback()
                return {
                    "code": StatusCode.SERVER_ERROR,
                    "message": f"流程删除失败: {str(e)}",
                    "data": None
                }
        except Exception as e:
            return {
                "code": StatusCode.SERVER_ERROR,
                "message": f"流程删除操作异常: {str(e)}",
                "data": None
            }

    @staticmethod
    def get_instances(
            page_num: int = 1,
            page_size: int = 6,
            process_id: Optional[int] = None,
            status: Optional[str] = None,
            db: Session = Depends(get_db)
    ) -> Dict[str, Any]:
        """获取流程实例列表"""
        result = instance_mapper.get_instances_paginated(
            db=db,
            page=page_num,
            page_size=page_size,
            process_id=process_id,
            status=status
        )

        # 转换为通用响应格式
        return {
            "code": StatusCode.SUCCESS,
            "message": "获取流程实例列表成功",
            "data": result
        }

    @staticmethod
    def stop_instance(instance_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
        """停止流程实例"""
        # 检查实例是否存在
        instance = instance_mapper.get(db, instance_id)
        if not instance:
            return {
                "code": StatusCode.NOT_FOUND,
                "message": f"流程实例不存在: ID {instance_id}",
                "data": None
            }

        # 检查实例状态，只有运行中的实例才能停止
        if instance.status != "0":  # 0表示运行中
            status_map = {"-1": "等待中", "0": "运行中", "1": "已完成", "2": "暂停中"}
            current_status = status_map.get(instance.status, "未知状态")
            return {
                "code": StatusCode.OPERATION_FAILED,
                "message": f"流程实例当前状态为{current_status}，无法停止",
                "data": None
            }

        # 调用stop_job函数停止任务
        job_stopped = stop_job(instance_id)

        if job_stopped:
            return {
                "code": StatusCode.SUCCESS,
                "message": "流程实例停止成功",
                "data": {"instance_id": instance_id}
            }
        else:
            return {
                "code": StatusCode.OPERATION_FAILED,
                "message": "流程实例停止失败，可能任务已经完成或不在运行",
                "data": None
            }
