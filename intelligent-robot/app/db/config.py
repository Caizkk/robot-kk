"""
数据库配置模块
用于加载和管理数据库配置
"""

import os
from typing import Dict, Any

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 默认配置
DEFAULT_CONFIG = {
    # 数据库类型
    "DB_TYPE": "mysql",

    # MySQL配置
    "MYSQL_HOST": "localhost",
    "MYSQL_PORT": "3306",
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "",
    "MYSQL_DB": "intelligent_robot",

    # 通用数据库配置
    "DB_ECHO": "False",
    "DB_POOL_SIZE": "5",
    "DB_MAX_OVERFLOW": "10",
    "DB_POOL_TIMEOUT": "30",
    "DB_POOL_RECYCLE": "1800"
}


def get_db_config() -> Dict[str, Any]:
    """
    获取数据库配置
    
    Returns:
        Dict[str, Any]: 数据库配置
    """
    config = {}

    # 使用默认配置
    for key, default_value in DEFAULT_CONFIG.items():
        # 从环境变量获取，如果不存在则使用默认值
        config[key] = os.getenv(key, default_value)

    return config


# 导出配置
db_config = get_db_config()
