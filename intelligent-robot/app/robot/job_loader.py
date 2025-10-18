"""
任务加载器模块，用于从数据库加载待执行的任务并放入队列
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from app.db.connection import SessionLocal
from app.mapper.process.robot_mapper import RobotMapper
from app.robot.queue import add_to_queue, is_job_in_queue

logger = logging.getLogger(__name__)
robot_mapper = RobotMapper()


async def load_pending_jobs() -> List[Dict[str, Any]]:
    """
    从数据库加载待执行的任务
    
    Returns:
        List[Dict[str, Any]]: 待执行的任务列表
    """
    db = SessionLocal()
    try:
        jobs = robot_mapper.load_pending_jobs(db)
        logger.info(f"从数据库加载了 {len(jobs)} 个待执行任务")

        count = 0
        for job in jobs:
            job_id = job.get('id')

            if job_id is not None and not is_job_in_queue(job_id):
                if add_to_queue(job):
                    count += 1
                    logger.info(f"任务 {job_id} 已添加到队列")
                else:
                    logger.error(f"添加任务 {job_id} 到队列失败")
            else:
                logger.info(f"任务 {job_id} 已经在队列中，跳过")

        logger.info(f"成功将 {count} 个任务加入队列")
        return jobs
    except Exception as e:
        logger.error(f"加载待执行任务时出错: {str(e)}")
        db.rollback()  # 显式回滚事务
        return []
    finally:
        db.close()


async def update_job_status(job_id: int, status: str = "0", start_time: datetime = None, result: str = "-1") -> bool:
    """
    更新任务状态
    
    Args:
        job_id: 任务ID
        status: 任务状态 (-1:等待中 0:运行中 1:已完成 2:暂停中)
        start_time: 开始时间，如果为None则使用当前时间
        result: 任务结果 (-1:无结果 0:失败 1:成功)
        
    Returns:
        bool: 是否更新成功
    """
    db = SessionLocal()
    try:
        result = robot_mapper.update_job_status(
            db=db,
            job_id=job_id,
            status=status,
            start_time=start_time,
            result=result
        )
        logger.info(f"更新任务 {job_id} 状态为 {status}, 结果为 {result}")
        return result
    except Exception as e:
        logger.error(f"更新任务 {job_id} 状态时出错: {str(e)}")
        return False
    finally:
        db.close()


async def reset_running_jobs() -> bool:
    """
    重置所有运行中的任务状态为等待中
    
    Returns:
        bool: 是否重置成功
    """
    db = SessionLocal()
    try:
        # 使用SQLAlchemy的事务管理（适用于所有版本）
        affected_rows = robot_mapper.reset_running_jobs(db)
        logger.info(f"已重置 {affected_rows} 个运行中的任务为等待状态")

        # 如果有任务被重置，确保等待加载完成
        if affected_rows > 0:
            try:
                # 使用超时机制确保不会无限等待
                jobs = await asyncio.wait_for(load_pending_jobs(), timeout=30)
                logger.info(f"成功重新加载 {len(jobs)} 个任务")
            except asyncio.TimeoutError:
                logger.error("重新加载任务超时")
                # 即使超时，我们仍然认为重置成功

        return True
    except Exception as e:
        db.rollback()
        logger.error(f"重置运行中任务状态时出错: {str(e)}")
        return False
    finally:
        db.close()


async def schedule_job_loading(interval_seconds: int = 60):
    """
    定时加载任务到队列
    
    Args:
        interval_seconds: 加载间隔（秒）
    """
    logger.info(f"启动任务加载调度器，间隔 {interval_seconds} 秒")
    while True:
        try:
            await load_pending_jobs()
        except Exception as e:
            logger.error(f"加载任务到队列时出错: {str(e)}")

        await asyncio.sleep(interval_seconds)


def start_job_loader(interval_seconds: int = 60):
    """
    启动任务加载器
    
    Args:
        interval_seconds: 加载间隔（秒）
    """
    asyncio.create_task(schedule_job_loading(interval_seconds))
    logger.info("任务加载器已启动")


async def reset_and_reload_jobs():
    """
    重置所有运行中的任务并重新加载
    """
    await reset_running_jobs()
