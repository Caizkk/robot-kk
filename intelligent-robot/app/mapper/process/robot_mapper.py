"""
机器人任务相关映射器
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.config import db_config


class RobotMapper:
    """机器人任务映射器，处理与任务执行相关的数据库操作"""

    def set_transaction_isolation_level(self, db: Session) -> None:
        """
        设置事务隔离级别为READ COMMITTED，防止脏读

        Args:
            db: 数据库会话
        """
        # 仅适用于MySQL
        db.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))

    def check_connection(self, db: Session) -> bool:
        """
        检查数据库连接是否正常

        Args:
            db: 数据库会话

        Returns:
            bool: 连接是否正常
        """
        db.execute(text("SELECT 1"))
        return True

    def load_pending_jobs(self, db: Session) -> List[Dict[str, Any]]:
        """
        从数据库加载待执行的任务

        Args:
            db: 数据库会话

        Returns:
            List[Dict[str, Any]]: 待执行的任务列表
        """
        # 设置事务隔离级别
        self.set_transaction_isolation_level(db)

        query = text("""
            SELECT
              pi.id,
              pi.process_id,
              pi.`status`,
              pi.result,
              pi.start_time,
              pi.end_time,
              pi.duration,
              pi.log_path,
              p.`name`,
              p.local_filename,
              p.content 
            FROM
              process_instance pi
              LEFT JOIN process p ON pi.process_id = p.id 
            WHERE
              pi.is_deleted = 0 
              AND p.is_deleted = 0 
              AND pi.`status` = '-1'
        """)

        result = db.execute(query)

        jobs = []
        for row in result:
            job = {
                "id": row.id,
                "process_id": row.process_id,
                "status": row.status,
                "result": row.result,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "duration": row.duration,
                "log_path": row.log_path,
                "name": row.name,
                "local_filename": row.local_filename,
                "content": row.content
            }
            jobs.append(job)

        return jobs

    def update_job_status(
            self,
            db: Session,
            job_id: int,
            status: str = "0",
            start_time: datetime = None,
            result: str = "-1"
    ) -> bool:
        """
        更新任务状态

        Args:
            db: 数据库会话
            job_id: 任务ID
            status: 任务状态 (-1:等待中 0:运行中 1:已完成 2:暂停中)
            start_time: 开始时间，如果为None则使用当前时间
            result: 任务结果 (-1:无结果 0:失败 1:成功)

        Returns:
            bool: 是否更新成功
        """
        try:
            # 设置事务隔离级别
            self.set_transaction_isolation_level(db)

            # 处理开始时间，确保是字符串格式
            if start_time is None:
                start_time = datetime.now()

            # 如果是datetime对象，转换为字符串
            if isinstance(start_time, datetime):
                start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")

            query = text("""
                UPDATE process_instance
                SET status = :status, start_time = :start_time, result = :result
                WHERE id = :job_id
            """)

            db.execute(query, {
                "job_id": job_id,
                "status": status,
                "start_time": start_time,
                "result": result
            })

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    def update_job_completion(
            self,
            db: Session,
            job_id: int,
            status: str,
            result: str,
            end_time: datetime,
            duration: int,
            log: str,
            log_path: Optional[str] = None
    ) -> bool:
        """
        更新任务完成状态

        Args:
            db: 数据库会话
            job_id: 任务ID
            status: 任务状态 (1:已完成)
            result: 任务结果 (0:失败 1:成功)
            end_time: 结束时间
            duration: 执行时长（秒）
            log: 执行日志
            log_path: 日志文件路径

        Returns:
            bool: 是否更新成功
        """
        try:
            # 设置事务隔离级别
            self.set_transaction_isolation_level(db)

            # 如果是datetime对象，转换为字符串
            if isinstance(end_time, datetime):
                end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")

            update_query = text("""
                UPDATE process_instance
                SET status = :status, 
                    result = :result, 
                    end_time = :end_time, 
                    duration = :duration,
                    log = :log,
                    log_path = :log_path
                WHERE id = :job_id
            """)

            db.execute(update_query, {
                "job_id": job_id,
                "status": status,
                "result": result,
                "end_time": end_time,
                "duration": duration,
                "log": log,
                "log_path": log_path
            })

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e

    def reset_running_jobs(self, db: Session) -> int:
        """
        重置所有运行中的任务状态为等待中

        Args:
            db: 数据库会话

        Returns:
            int: 重置的任务数量
        """
        try:
            # 设置事务隔离级别
            self.set_transaction_isolation_level(db)

            query = text("""
                UPDATE process_instance
                SET 
                    status = '-1',
                    result = '-1',
                    start_time = NULL,
                    end_time = NULL,
                    duration = NULL,
                    log = NULL,
                    log_path = NULL
                WHERE 
                    status = '0'
            """)

            result = db.execute(query)
            affected_rows = result.rowcount

            db.commit()
            return affected_rows
        except Exception as e:
            db.rollback()
            raise e
