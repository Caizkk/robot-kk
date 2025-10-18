"""
任务工作器模块，用于监听和消费队列中的任务
"""

import concurrent.futures
import logging
import threading
import time
import os
import robot
# 【修复】导入Robot的pyloggingconf模块以管理日志重定向
from robot.output import pyloggingconf
from datetime import datetime
from typing import Dict, Any, List

# 确保在运行此模块前，相关依赖已正确配置
# 例如：数据库会话、Mapper实例、队列和配置
from app.db.connection import SessionLocal
from app.mapper.process.robot_mapper import RobotMapper
from app.robot.config import get_thread_pool_config
from app.robot.queue import get_process_queue, queue_lock
import pythoncom

logger = logging.getLogger(__name__)
robot_mapper = RobotMapper()

# 工作器状态
WORKER_RUNNING = True

# 线程池
thread_pool = None

# 工作线程实例
worker_thread_instance = None

# 任务ID和线程ID的映射关系
job_thread_map = {}

# 任务停止标志字典，用于控制单个任务的停止
job_stop_flags = {}

# 线程池锁，用于保护job_thread_map和job_stop_flags的并发访问
thread_map_lock = threading.Lock()


class JobThreadPool:
    """
    任务线程池，管理任务执行的线程
    """

    def __init__(self, max_workers=5, thread_name_prefix='worker'):
        """
        初始化任务线程池

        Args:
            max_workers: 最大工作线程数
            thread_name_prefix: 线程名称前缀
        """
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        self.futures = {}  # 保存future对象
        self.lock = threading.Lock()
        logger.info(f"线程池初始化成功，最大工作线程数: {max_workers}, 线程名称前缀: {thread_name_prefix}")

    def submit_job(self, job_id: int, func, *args, **kwargs) -> bool:
        """
        提交任务到线程池

        Args:
            job_id: 任务ID
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            bool: 是否成功提交
        """
        with self.lock:
            if job_id in self.futures:
                future = self.futures[job_id]
                if future.done():
                    del self.futures[job_id]
                else:
                    logger.warning(f"任务 {job_id} 已经在执行中")
                    return False

            try:
                future = self.executor.submit(func, *args, **kwargs)
                self.futures[job_id] = future
                future.add_done_callback(lambda f: self._job_done_callback(job_id, f))

                with thread_map_lock:
                    thread_id = threading.get_ident()
                    job_thread_map[job_id] = thread_id
                    job_stop_flags[job_id] = False

                return True
            except Exception as e:
                logger.error(f"提交任务 {job_id} 到线程池时出错: {str(e)}")
                return False

    def _job_done_callback(self, job_id: int, future):
        """
        任务完成的回调函数
        """
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name

        try:
            with self.lock:
                if job_id in self.futures:
                    del self.futures[job_id]
                with thread_map_lock:
                    if job_id in job_thread_map:
                        del job_thread_map[job_id]
                    if job_id in job_stop_flags:
                        del job_stop_flags[job_id]

            if future.exception():
                logger.error(
                    f"任务 {job_id} 执行失败: {future.exception()}，回调线程ID: {thread_id}，线程名称: {thread_name}")
            else:
                logger.info(f"任务 {job_id} 执行完成，回调线程ID: {thread_id}，线程名称: {thread_name}")
        except Exception as e:
            logger.error(f"处理任务 {job_id} 完成回调时出错: {str(e)}，线程ID: {thread_id}")

    def get_running_jobs(self) -> List[int]:
        """
        获取正在运行的任务ID列表
        """
        with self.lock:
            return [job_id for job_id, future in self.futures.items() if not future.done()]

    def shutdown(self, wait=True):
        """
        关闭线程池
        """
        try:
            with self.lock:
                for job_id, future in self.futures.items():
                    if not future.done():
                        future.cancel()

            self.executor.shutdown(wait=wait)
            logger.info("任务线程池已关闭")
        except Exception as e:
            logger.error(f"关闭任务线程池时出错: {str(e)}")


def update_thread_id(job_id: int):
    """
    更新任务的线程ID（在任务实际执行的线程中调用）
    """
    with thread_map_lock:
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        job_thread_map[job_id] = thread_id
        if job_id not in job_stop_flags:
            job_stop_flags[job_id] = False
        logger.info(f"更新任务 {job_id} 的线程ID为 {thread_id}，线程名称: {thread_name}")


def process_job(job: Dict[str, Any]) -> None:
    """
    处理任务的具体逻辑，通过在当前线程中直接调用Robot Framework API来执行。

    Args:
        job: 任务信息，包含流程实例和流程信息
    """
    # 2. 在 try 块的最开始，为当前线程初始化COM
    pythoncom.CoInitialize()

    job_id = job.get('id')
    update_thread_id(job_id)
    thread_id = threading.get_ident()
    thread_name = threading.current_thread().name
    start_time = datetime.now()
    logs = [f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行任务，线程ID: {thread_id}，线程名称: {thread_name}"]
    log_path = None

    try:
        # --- 1. 准备脚本文件 ---
        script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'script'))
        os.makedirs(script_dir, exist_ok=True)

        robot_filename = job.get('local_filename')
        if not robot_filename:
            raise ValueError("任务信息中缺少 'local_filename'")

        robot_file_path = os.path.join(script_dir, robot_filename)

        if not os.path.exists(robot_file_path):
            job_content = job.get('content')
            if not job_content:
                raise ValueError(f"脚本文件 {robot_filename} 不存在，且任务内容为空。")
            with open(robot_file_path, 'w', encoding='utf-8') as f:
                f.write(job_content)
            logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 脚本文件不存在，已创建: {robot_file_path}")
            logger.info(f"任务 {job_id} - 脚本文件不存在，已创建新文件: {robot_file_path}")
        else:
            logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 使用已存在脚本: {robot_file_path}")
            logger.info(f"任务 {job_id} - 使用已存在脚本文件: {robot_file_path}")

        # --- 2. 使用单个数据库会话更新状态并执行任务 ---
        with SessionLocal() as db:
            robot_mapper.update_job_status(db=db, job_id=job_id, status="0", start_time=start_time, result="-1")
            db.commit()
            logger.info(f"任务 {job_id} - 状态更新为运行中。")

            output_dir = os.path.join(script_dir, 'output', str(job_id))
            os.makedirs(output_dir, exist_ok=True)
            log_filename = f"log_{job_id}.html"
            log_path = os.path.join(output_dir, log_filename)

            logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行Robot测试...")
            logger.info(f"任务 {job_id} - 开始执行Robot测试...")

            return_code = robot.run(
                robot_file_path,
                outputdir=output_dir,
                log=log_filename,
                report=f"report_{job_id}.html",
                stdout=None,
                stderr=None
            )

            logs.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Robot测试执行完毕，返回码: {return_code}")
            logger.info(f"任务 {job_id} - Robot测试执行完毕，返回码: {return_code}")

            # --- 3. 根据结果更新最终状态 ---
            end_time = datetime.now()
            duration = max(1, int((end_time - start_time).total_seconds()))
            result = "1" if return_code == 0 else "0"
            status = "1"

            logs.append(f"[{end_time.strftime('%Y-%m-%d %H:%M:%S')}] 任务执行完成，耗时 {duration} 秒")
            logger.info(f"任务 {job_id} - 任务执行完成，耗时 {duration} 秒。")

            robot_mapper.update_job_completion(
                db=db, job_id=job_id, status=status, result=result, end_time=end_time,
                duration=duration, log="\n".join(logs), log_path=log_path
            )
            db.commit()
            logger.info(f"任务 {job_id} - 完成状态更新成功。")

    except Exception as e:
        end_time = datetime.now()
        duration = max(1, int((end_time - start_time).total_seconds()))
        error_message = f"处理任务时发生严重错误: {str(e)}"
        logs.append(f"[{end_time.strftime('%Y-%m-%d %H:%M:%S')}] {error_message}")
        logger.error(f"任务 {job_id} - {error_message}", exc_info=True)

        try:
            with SessionLocal() as db:
                robot_mapper.update_job_completion(
                    db=db, job_id=job_id, status="1", result="0", end_time=end_time,
                    duration=duration, log="\n".join(logs), log_path=log_path
                )
                db.commit()
                logger.info(f"任务 {job_id} - 已将任务状态更新为失败。")
        except Exception as db_error:
            logger.error(f"任务 {job_id} - 更新失败状态时再次发生数据库错误: {db_error}", exc_info=True)

    finally:
        # 3. 在 finally 块中，确保COM被反初始化，交回“通行证”
        pythoncom.CoUninitialize()
        logger.info(f"任务 {job_id} - 处理线程结束，已清理COM配置。")


def worker_thread() -> None:
    """
    工作线程，持续监听队列并处理任务
    """
    global thread_pool
    thread_id = threading.get_ident()
    thread_name = threading.current_thread().name
    logger.info(f"任务工作器启动，线程ID: {thread_id}，线程名称: {thread_name}")

    while WORKER_RUNNING:
        try:
            queue = get_process_queue()
            if not queue.empty():
                job = queue.get()
                job_id = job.get('id', 0)
                logger.info(f"从队列获取到任务: {job_id}，工作线程ID: {thread_id}")

                if thread_pool.submit_job(job_id, process_job, job):
                    logger.info(f"任务 {job_id} 已提交到线程池，工作线程ID: {thread_id}")
                    queue.task_done()
                else:
                    logger.warning(f"任务 {job_id} 提交失败，将任务放回队列")
                    with queue_lock:
                        queue.put(job)
            else:
                time.sleep(1)
        except Exception as e:
            logger.error(f"处理任务时出错: {str(e)}，工作线程ID: {thread_id}", exc_info=True)
            time.sleep(5)


def get_job_thread_map() -> Dict[int, int]:
    """
    获取任务ID和线程ID的映射关系
    """
    with thread_map_lock:
        return job_thread_map.copy()


def start_worker() -> threading.Thread:
    """
    启动工作器线程
    """
    global WORKER_RUNNING, thread_pool, worker_thread_instance
    WORKER_RUNNING = True

    thread_pool_config = get_thread_pool_config()
    thread_pool = JobThreadPool(
        max_workers=thread_pool_config['max_workers'],
        thread_name_prefix=thread_pool_config['thread_name_prefix']
    )

    worker_thread_instance = threading.Thread(target=worker_thread, daemon=True)
    worker_thread_instance.start()
    logger.info("工作器线程已启动")
    return worker_thread_instance


def stop_job(job_id: int) -> bool:
    """
    停止指定任务
    """
    with thread_map_lock:
        if job_id in job_stop_flags:
            job_stop_flags[job_id] = True
            logger.info(f"已设置任务 {job_id} 的停止标志 (注意: 线程内执行的任务可能无法立即响应)")
            return True
        else:
            logger.warning(f"任务 {job_id} 不存在或已完成，无法设置停止标志")
            return False


def stop_worker() -> None:
    """
    停止工作器线程
    """
    global WORKER_RUNNING, thread_pool, worker_thread_instance
    WORKER_RUNNING = False
    logger.info("任务工作器停止中...")

    if thread_pool:
        thread_pool.shutdown(wait=True)

    if worker_thread_instance and worker_thread_instance.is_alive():
        worker_thread_instance.join(timeout=10)

    with thread_map_lock:
        job_thread_map.clear()
        job_stop_flags.clear()

    logger.info("任务工作器已停止")
