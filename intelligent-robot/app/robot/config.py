"""
机器人配置模块，用于读取环境变量中的配置
"""

import os

from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 线程池配置
THREAD_POOL_MAX_WORKERS = int(os.getenv('THREAD_POOL_MAX_WORKERS', '5'))
THREAD_POOL_THREAD_NAME_PREFIX = os.getenv('THREAD_POOL_THREAD_NAME_PREFIX', 'worker')


# 获取线程池配置
def get_thread_pool_config():
    """
    获取线程池配置
    
    Returns:
        dict: 线程池配置
    """
    return {
        'max_workers': THREAD_POOL_MAX_WORKERS,
        'thread_name_prefix': THREAD_POOL_THREAD_NAME_PREFIX
    }
