import logging
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import uvicorn

# --- 日志配置 (已修改) ---
# 1. 定义日志文件的存储目录 (项目根目录下的 logs 文件夹)
log_dir = os.path.join(current_dir, 'logs')

# 2. 确保日志目录存在，如果不存在则创建
os.makedirs(log_dir, exist_ok=True)

# 3. 获取当前日期，格式为 YYYY-MM-DD
current_date = datetime.now().strftime('%Y-%m-%d')

# 4. 组合成完整的文件名，例如: app-2025-10-12.log
log_filename = f"app-{current_date}.log"
log_file_path = os.path.join(log_dir, log_filename)

# 5. 配置日志系统 (兼容旧版Python，并同时输出到文件和控制台)
# 获取根 logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 清除可能已存在的处理器，防止重复打印
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# 创建一个 Formatter
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 创建文件处理器，并显式设置编码
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setFormatter(log_format)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_format)

# 将两个处理器都添加到根 logger
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
# --- 日志配置结束 ---


# 现在导入app模块
from app.api.app import app
from app.db.init_db import init_db
from app.robot.job_loader import reset_and_reload_jobs
from app.robot.job_worker import start_worker, stop_worker
from app.robot.queue import create_process_queue

logger = logging.getLogger(__name__)

# 在日志配置完成后，立即记录日志文件的位置
logger.info(f"日志系统已配置完成。日志文件将保存到: {log_file_path}")


# --- 优化的MySQL检查和启动功能 ---

def is_port_in_use(port: int, host: str = '127.0.0.1') -> bool:
    """检查指定端口是否已被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)  # 使用1秒的短超时
        return s.connect_ex((host, port)) == 0


def wait_for_port(port: int, host: str = '127.0.0.1', timeout: int = 15) -> bool:
    """在指定的超时时间内轮询端口，直到它变为可用状态"""
    logger.info(f"正在等待MySQL端口 {port} 开放 (最多等待 {timeout} 秒)...")
    start_time = time.monotonic()
    while True:
        if is_port_in_use(port, host):
            return True
        if time.monotonic() - start_time >= timeout:
            return False
        time.sleep(1)


def start_mysql_service() -> bool:
    """
    尝试启动本地MySQL服务。
    会依次尝试多个常见的服务名称，并在成功后轮询端口。
    """
    possible_service_names = ["MySQL80", "MySQL", "MySQL57"]

    for service_name in possible_service_names:
        try:
            command = f"net start {service_name}"
            logger.info(f"正在尝试使用服务名 '{service_name}' 启动MySQL...")
            logger.info(f"执行命令: '{command}'...")

            result = subprocess.run(
                command, shell=True, check=True, capture_output=True, text=True, encoding='gbk', errors='ignore'
            )

            success_messages = ["已成功启动", "已经启动", "The MySQL80 service was started successfully."]
            output_text = result.stdout.strip()

            if any(msg in output_text for msg in success_messages):
                logger.info(f"服务 '{service_name}' 启动命令执行成功。")
                if wait_for_port(3306, timeout=360):
                    logger.info("MySQL端口3306已成功开放。")
                    return True
                else:
                    logger.warning("服务已启动，但端口3306在超时时间内仍未开放。请手动检查MySQL日志。")
                    return False
            else:
                logger.warning(f"命令 '{command}' 执行完成，但输出信息不符合成功标志: {output_text}")

        except subprocess.CalledProcessError as e:
            error_output = e.stderr.strip()
            if "拒绝访问" in error_output or "Access is denied" in error_output or "错误 5" in error_output:
                logger.error("=" * 60)
                logger.error("!!! 权限错误：拒绝访问 !!!")
                logger.error(f"启动服务 '{service_name}' 失败，因为当前用户没有管理员权限。")
                logger.error("解决方案：请关闭当前程序，然后【以管理员身份】重新运行您的IDE(PyCharm)或命令行。")
                logger.error("=" * 60)
                return False  # Stop trying if permission is denied
            elif "服务名无效" in error_output or "service name is invalid" in error_output:
                logger.warning(f"服务名 '{service_name}' 无效，将尝试下一个。")
                continue
            else:
                logger.error(f"启动服务 '{service_name}' 时发生未知系统错误，返回码: {e.returncode}")
                logger.error(f"错误输出: {error_output}")
                break
        except Exception as e:
            logger.error(f"尝试启动服务 '{service_name}' 时发生未知错误: {e}")
            break

    logger.error("尝试了所有可能的MySQL服务名，但均未能成功启动。")
    return False


# 工作器线程
worker_thread = None


# 使用生命周期事件处理器
@asynccontextmanager
async def lifespan(app_instance):
    global worker_thread
    logger.info("应用生命周期事件：启动...")
    try:
        mysql_ready = False
        if is_port_in_use(3306):
            logger.info("检测到MySQL服务已在3306端口运行。")
            mysql_ready = True
        else:
            logger.warning("检测到MySQL服务未在3306端口运行，正在尝试启动...")
            if start_mysql_service():
                mysql_ready = True

        if not mysql_ready:
            raise RuntimeError("MySQL服务未能成功启动，应用初始化中断。请检查日志并手动启动MySQL后重试。")

        init_db()
        create_process_queue()
        await reset_and_reload_jobs()
        worker_thread = start_worker()
        logger.info("应用初始化完成。")
    except Exception as e:
        logger.error(f"应用初始化失败: {str(e)}", exc_info=True)
        # Re-raise to prevent the application from starting in a bad state
        raise

    yield

    logger.info("应用生命周期事件：关闭...")
    if worker_thread:
        stop_worker()
        logger.info("应用资源已释放。")


# 更新FastAPI应用的生命周期管理
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8111)
