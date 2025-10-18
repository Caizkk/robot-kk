"""
数据库连接工厂模块
支持MySQL数据库连接
通过环境变量配置切换数据源
"""

import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.db.config import db_config

# 设置日志
logger = logging.getLogger(__name__)

# 创建基础模型
Base = declarative_base()


# 数据库连接工厂类
class DBConnectionFactory:
    """数据库连接工厂，支持MySQL"""

    @staticmethod
    def get_engine() -> Engine:
        """
        根据环境变量获取数据库引擎

        Returns:
            Engine: SQLAlchemy数据库引擎
        """
        db_type = db_config["DB_TYPE"].lower()

        if db_type == "mysql":
            return DBConnectionFactory._create_mysql_engine()
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")

    @staticmethod
    def _create_mysql_engine() -> Engine:
        """
        创建MySQL数据库引擎
        
        Returns:
            Engine: MySQL数据库引擎
        """
        host = db_config["MYSQL_HOST"]
        port = db_config["MYSQL_PORT"]
        user = db_config["MYSQL_USER"]
        password = db_config["MYSQL_PASSWORD"]
        db = db_config["MYSQL_DB"]

        connection_string = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
        return DBConnectionFactory._create_engine(connection_string)

    @staticmethod
    def _create_engine(connection_string: str) -> Engine:
        """
        创建数据库引擎
        
        Args:
            connection_string: 数据库连接字符串
            
        Returns:
            Engine: SQLAlchemy数据库引擎
        """
        # 获取通用数据库配置
        echo = db_config["DB_ECHO"].lower() == "true"
        pool_size = int(db_config["DB_POOL_SIZE"])
        max_overflow = int(db_config["DB_MAX_OVERFLOW"])
        pool_timeout = int(db_config["DB_POOL_TIMEOUT"])
        pool_recycle = int(db_config["DB_POOL_RECYCLE"])

        # 创建引擎
        engine = create_engine(
            connection_string,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            # 添加连接前健康检查
            pool_pre_ping=True
        )

        # 添加事件监听器
        DBConnectionFactory._add_engine_events(engine)

        return engine

    @staticmethod
    def _add_engine_events(engine: Engine) -> None:
        """
        添加引擎事件监听器
        
        Args:
            engine: SQLAlchemy数据库引擎
        """

        # 连接创建事件
        @event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            logger.debug("创建新数据库连接")

        # 连接检出事件（从池中获取连接）
        @event.listens_for(engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            pass

        # 连接检入事件（归还连接到池）
        @event.listens_for(engine, "checkin")
        def checkin(dbapi_connection, connection_record):
            pass

        # 连接断开事件
        @event.listens_for(engine, "close")
        def close(dbapi_connection, connection_record):
            logger.debug("关闭数据库连接")

        # 连接无效事件
        @event.listens_for(engine, "invalidate")
        def invalidate(dbapi_connection, connection_record, exception):
            logger.warning(f"数据库连接无效: {str(exception) if exception else 'Unknown reason'}")


# 创建数据库引擎
engine = DBConnectionFactory.get_engine()

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    获取数据库会话
    
    Returns:
        Session: 数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    检查数据库连接是否正常
    
    Returns:
        bool: 连接是否正常
    """
    from app.mapper.process.robot_mapper import RobotMapper

    db = SessionLocal()
    try:
        # 使用RobotMapper检查连接
        robot_mapper = RobotMapper()
        return robot_mapper.check_connection(db)
    except Exception as e:
        logger.error(f"数据库连接检查失败: {str(e)}")
        return False
    finally:
        db.close()
