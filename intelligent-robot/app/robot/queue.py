"""
流程队列模块，用于管理流程实例的执行队列
"""

import logging
import threading
from typing import Dict, Any, Set

from queue import Queue

# 全局流程队列
process_queue = None

# 队列中的任务ID集合，用于检查重复
queue_job_ids = set()

# 队列锁，用于保护队列和任务ID集合的并发访问
queue_lock = threading.Lock()

# 队列初始化锁，用于保护队列初始化过程
init_lock = threading.Lock()

logger = logging.getLogger(__name__)


def create_process_queue() -> Queue:
    """
    创建一个全局流程队列
    队列中的元素结构包含：
    - pi.id: 流程实例id
    - pi.process_id: 流程id
    - pi.status: 运行状态
    - pi.result: 运行结果
    - pi.start_time: 开始时间
    - pi.end_time: 结束时间
    - pi.duration: 运行时长
    - p.name: 流程名称
    - p.local_filename: 流程文件名称
    - p.content: 流程内容
    
    Returns:
        Queue: 流程队列
    """
    global process_queue, queue_job_ids

    # 使用双重检查锁定模式确保线程安全的单例初始化
    if process_queue is None:
        with init_lock:
            if process_queue is None:
                logger.info("创建全局流程队列")
                process_queue = Queue()
                queue_job_ids = set()

    return process_queue


def get_process_queue() -> Queue:
    """
    获取全局流程队列
    
    Returns:
        Queue: 流程队列
    """
    global process_queue

    # 使用双重检查锁定模式确保线程安全的单例获取
    if process_queue is None:
        with init_lock:
            if process_queue is None:
                process_queue = create_process_queue()

    return process_queue


def add_to_queue(process_item: Dict[str, Any]) -> bool:
    """
    添加流程到队列，确保任务ID唯一
    
    Args:
        process_item: 流程项，包含流程实例和流程信息
        
    Returns:
        bool: 是否添加成功
    """
    job_id = process_item.get('id')
    if job_id is None:
        return False

    queue = get_process_queue()
    with queue_lock:
        # 检查任务ID是否已经在队列中
        if job_id in queue_job_ids:
            return False

        try:
            # 先尝试放入队列（使用非阻塞方式）
            queue.put_nowait(process_item)
            # 成功后再更新集合
            queue_job_ids.add(job_id)
            return True
        except Exception as e:
            logger.error(f"添加任务 {job_id} 到队列失败: {str(e)}")
            return False


def get_from_queue() -> Dict[str, Any]:
    """
    从队列中获取一个流程项
    
    Returns:
        Dict[str, Any]: 流程项，如果队列为空则返回None
    """
    global queue_job_ids

    queue = get_process_queue()

    with queue_lock:
        if queue.empty():
            return None

        job = queue.get()

        job_id = job.get('id')
        if job_id is not None and job_id in queue_job_ids:
            queue_job_ids.remove(job_id)

        return job


def is_job_in_queue(job_id: int) -> bool:
    """
    检查任务是否在队列中
    
    Args:
        job_id: 任务ID
        
    Returns:
        bool: 是否在队列中
    """
    global queue_job_ids

    with queue_lock:
        return job_id in queue_job_ids


def get_queue_size() -> int:
    """
    获取队列大小
    
    Returns:
        int: 队列中的任务数量
    """
    queue = get_process_queue()
    return queue.qsize()


def get_queue_job_ids() -> Set[int]:
    """
    获取队列中的所有任务ID
    
    Returns:
        Set[int]: 任务ID集合
    """
    global queue_job_ids

    with queue_lock:
        return queue_job_ids.copy()
