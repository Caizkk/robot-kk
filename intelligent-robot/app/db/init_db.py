"""
数据库初始化模块
用于创建数据库表和初始数据
"""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import Base, engine

# 导入所有模型，确保它们被注册到Base元数据

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    初始化数据库
    创建所有表
    """
    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建成功")
    except SQLAlchemyError as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise


def drop_db() -> None:
    """
    删除所有表
    警告：此操作将删除所有数据
    """
    try:
        # 删除所有表
        Base.metadata.drop_all(bind=engine)
        logger.info("数据库表删除成功")
    except SQLAlchemyError as e:
        logger.error(f"数据库表删除失败: {str(e)}")
        raise


if __name__ == "__main__":
    # 当直接运行此脚本时，初始化数据库
    init_db()
