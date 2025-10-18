"""
流程相关映射器
"""

from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from app.db.base_mapper import BaseMapper
from app.domains.process.models import Process, ProcessInstance


class ProcessMapper(BaseMapper[Process]):
    """流程映射器"""

    def __init__(self):
        super().__init__(Process)

    def get_processes_paginated(
            self,
            db: Session,
            page: int = 1,
            page_size: int = 10,
            name: Optional[str] = None,
            is_deleted: str = '0'
    ) -> Dict[str, Any]:
        """
        获取分页的流程列表

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页大小
            name: 流程名称过滤
            is_deleted: 是否已删除，0表示存在（未删除），1表示已删除

        Returns:
            Dict[str, Any]: 分页结果
        """
        # 构建过滤条件
        filters = {"is_deleted": is_deleted}

        # 如果有名称过滤，需要特殊处理（因为需要使用 LIKE 查询）
        if name:
            # 计算总数（带名称过滤）
            query = db.query(Process).filter(
                Process.is_deleted == is_deleted,
                Process.name.like(f"%{name}%")
            )
            total = query.count()

            # 获取数据（带名称过滤、排序和分页）
            query = query.order_by(desc(Process.created_at))
            query = query.offset((page - 1) * page_size).limit(page_size)
            processes = query.all()
        else:
            # 计算总数
            total = self.count(db, filters=filters)

            # 获取数据（带排序和分页）
            query = db.query(Process).filter(Process.is_deleted == is_deleted)
            query = query.order_by(desc(Process.created_at))
            query = query.offset((page - 1) * page_size).limit(page_size)
            processes = query.all()

        # 转换为字典
        result = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": [p.to_dict() for p in processes]
        }

        return result

    def get_latest_processes(
            self,
            db: Session,
            page: int = 1,
            page_size: int = 6,
            search_keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取最新版本的流程列表，按照更新时间降序排序

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页大小
            search_keyword: 流程名称搜索关键词

        Returns:
            Dict[str, Any]: 分页结果
        """
        # 构建SQL查询
        sql_query = """
        SELECT
          p1.id,
          p1.name,
          p1.version,
          ( SELECT MAX( p2.created_at ) FROM process p2 WHERE p2.name = p1.name AND p2.version = 'V 1.0.0' ) AS create_time,
          p1.created_at AS update_time,
          0 AS run_count,
          0 AS pause_count 
        FROM
          process p1
          INNER JOIN ( SELECT name, MAX( version ) AS max_version FROM process WHERE is_deleted = '0' GROUP BY name ) sub ON p1.name = sub.name 
          AND p1.version = sub.max_version 
        WHERE
          p1.is_deleted = '0'
        """

        # 添加搜索条件
        if search_keyword:
            sql_query += f" AND p1.name LIKE :search_keyword"

        # 添加排序
        sql_query += " ORDER BY update_time DESC"

        # 计算总记录数（不带分页）
        count_sql = f"SELECT COUNT(*) FROM ({sql_query}) as count_query"

        # 添加分页
        sql_query += " LIMIT :limit OFFSET :offset"

        # 执行查询
        params = {
            "offset": (page - 1) * page_size,
            "limit": page_size
        }

        if search_keyword:
            params["search_keyword"] = f"%{search_keyword}%"

        # 执行计数查询
        total_result = db.execute(text(count_sql), params).scalar()

        # 执行数据查询
        result_proxy = db.execute(text(sql_query), params)

        # 处理结果
        processes = []
        for row in result_proxy:
            # 检查日期时间字段的类型并适当处理
            create_time = row.create_time
            if create_time and not isinstance(create_time, str):
                create_time = create_time.strftime("%Y-%m-%d %H:%M:%S")

            update_time = row.update_time
            if update_time and not isinstance(update_time, str):
                update_time = update_time.strftime("%Y-%m-%d %H:%M:%S")

            process_dict = {
                "id": row.id,
                "name": row.name,  # 使用小写的name与SQL查询匹配
                "version": row.version,
                "create_time": create_time,
                "update_time": update_time,
                "run_count": row.run_count,
                "pause_count": row.pause_count
            }
            processes.append(process_dict)

        # 构建返回结果
        result = {
            "total": total_result,
            "page_num": page,
            "page_size": page_size,
            "data": processes
        }

        return result

    def get_all_process_id_names(
            self,
            db: Session,
            search_keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取所有流程的ID和名称列表，支持名称模糊搜索

        Args:
            db: 数据库会话
            search_keyword: 流程名称搜索关键词

        Returns:
            Dict[str, Any]: 结果列表
        """
        # 构建SQL查询 - 获取每个流程名称的最新版本
        sql_query = """
        SELECT
          p1.id,
          p1.name
        FROM
          process p1
        WHERE
          p1.is_deleted = '0'
        """

        # 添加搜索条件
        if search_keyword:
            sql_query += " AND p1.name LIKE :search_keyword"

        # 添加排序
        sql_query += " ORDER BY p1.name ASC"

        # 执行查询
        params = {}
        if search_keyword:
            params["search_keyword"] = f"%{search_keyword}%"

        # 执行数据查询
        result_proxy = db.execute(text(sql_query), params)

        # 处理结果
        processes = []
        for row in result_proxy:
            process_dict = {
                "id": row.id,
                "name": row.name  # 使用小写的name与SQL查询匹配
            }
            processes.append(process_dict)

        # 计算总数
        total = len(processes)

        # 构建返回结果
        result = {
            "total": total,
            "data": processes
        }

        return result

    def soft_delete(self, db: Session, process_id: int) -> Optional[Process]:
        """
        软删除流程

        Args:
            db: 数据库会话
            process_id: 流程ID

        Returns:
            Optional[Process]: 更新后的流程，如果不存在则返回None
        """
        # 使用 get 方法获取未删除的流程
        process = self.get(db, process_id)
        if not process:
            return None

        # 更新为已删除状态
        process.is_deleted = '1'  # 1表示已删除
        db.add(process)
        db.commit()
        db.refresh(process)
        return process


class ProcessInstanceMapper(BaseMapper[ProcessInstance]):
    """流程实例映射器"""

    def __init__(self):
        super().__init__(ProcessInstance)

    def count_unfinished_instances(self, db: Session, process_id: int) -> int:
        """
        统计指定流程的未完成实例数量

        Args:
            db: 数据库会话
            process_id: 流程ID

        Returns:
            int: 未完成实例的数量
        """
        # 直接统计未完成实例的总数（状态不为1的实例）
        sql_query = """
        SELECT 
            COUNT(*) as count
        FROM 
            process_instance
        WHERE 
            process_id = :process_id
            AND is_deleted = '0'
            AND status != '1'  -- 不是已完成状态
        """

        result = db.execute(text(sql_query), {"process_id": process_id}).scalar()
        return result

    def get_instances_paginated(
            self,
            db: Session,
            page: int = 1,
            page_size: int = 10,
            process_id: Optional[int] = None,
            status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取分页的流程实例列表

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页大小
            process_id: 流程ID过滤
            status: 状态过滤

        Returns:
            Dict[str, Any]: 分页结果
        """
        # 构建过滤条件
        filters = {}  # BaseMapper 会自动添加 is_deleted='0' 过滤条件
        if process_id:
            filters["process_id"] = process_id
        if status:
            filters["status"] = status

        # 计算总数
        total = self.count(db, filters=filters)

        # 使用 get_multi 获取数据，自动过滤已删除的记录
        instances = self.get_multi(
            db=db,
            skip=(page - 1) * page_size,
            limit=page_size,
            filters=filters,
            order_by=desc(ProcessInstance.start_time)
        )

        # 转换为字典
        result = {
            "total": total,
            "page_num": page,
            "page_size": page_size,
            "data": [i.to_dict() for i in instances]
        }

        return result

    def update_instance_status(
            self,
            db: Session,
            instance_id: int,
            status: str,
            result: Optional[str] = None,
            end_time: Optional[Any] = None,
            duration: Optional[int] = None,
            log: Optional[str] = None,
            log_path: Optional[str] = None
    ) -> Optional[ProcessInstance]:
        """
        更新实例状态

        Args:
            db: 数据库会话
            instance_id: 实例ID
            status: 新状态
            result: 结果
            end_time: 结束时间
            duration: 持续时间
            log: 日志
            log_path: 日志路径

        Returns:
            Optional[ProcessInstance]: 更新后的实例，如果不存在则返回None
        """
        # 使用 get 方法获取未删除的实例
        instance = self.get(db, instance_id)
        if not instance:
            return None

        instance.status = status

        if result is not None:
            instance.result = result

        if end_time is not None:
            # 如果是datetime对象，转换为字符串
            if isinstance(end_time, datetime):
                end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
            instance.end_time = end_time

        if duration is not None:
            instance.duration = duration

        if log is not None:
            instance.log = log

        if log_path is not None:
            instance.log_path = log_path

        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance
