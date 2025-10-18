# app/db/base_mapper.py

"""
基础映射器模块
提供通用CRUD操作的基础映射器类
"""

from typing import Generic, TypeVar, Type, List, Optional, Any, Dict

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.connection import Base

# 定义泛型类型变量
T = TypeVar('T', bound=Base)


class BaseMapper(Generic[T]):
    """
    基础映射器类，提供通用CRUD操作
    
    泛型参数:
        T: SQLAlchemy模型类型，必须继承自Base
    """

    def __init__(self, model_class: Type[T]):
        """
        初始化映射器
        
        Args:
            model_class: SQLAlchemy模型类
        """
        self.model_class = model_class

    def _has_is_deleted_field(self) -> bool:
        """
        检查模型是否有 is_deleted 字段
        
        Returns:
            bool: 是否有 is_deleted 字段
        """
        return hasattr(self.model_class, "is_deleted")

    def _filter_not_deleted(self, query):
        """
        添加过滤条件，排除已删除的记录
        
        Args:
            query: 查询对象
            
        Returns:
            query: 添加过滤条件后的查询对象
        """
        if self._has_is_deleted_field():
            return query.filter(getattr(self.model_class, "is_deleted") == '0')
        return query

    def create(self, db: Session, obj_in: Dict[str, Any]) -> T:
        """
        创建记录
        
        Args:
            db: 数据库会话
            obj_in: 要创建的对象数据
            
        Returns:
            T: 创建的记录
        """
        try:
            # 如果没有指定 is_deleted 且模型有该字段，则默认设为未删除
            if self._has_is_deleted_field() and "is_deleted" not in obj_in:
                obj_in["is_deleted"] = '0'

            db_obj = self.model_class(**obj_in)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            raise e

    def get(self, db: Session, id: Any) -> Optional[T]:
        """
        通过ID获取记录，排除已删除的记录
        
        Args:
            db: 数据库会话
            id: 记录ID
            
        Returns:
            Optional[T]: 找到的记录，如果不存在则返回None
        """
        query = db.query(self.model_class).filter(self.model_class.id == id)
        query = self._filter_not_deleted(query)
        return query.first()

    def get_multi(
            self,
            db: Session,
            *,
            skip: int = 0,
            limit: int = 100,
            filters: Optional[Dict[str, Any]] = None,
            order_by: Optional[Any] = None
    ) -> List[T]:
        """
        获取多条记录，排除已删除的记录
        
        Args:
            db: 数据库会话
            skip: 跳过的记录数
            limit: 返回的记录数上限
            filters: 过滤条件
            order_by: 排序条件
            
        Returns:
            List[T]: 记录列表
        """
        query = db.query(self.model_class)

        # 应用过滤条件
        if filters:
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    query = query.filter(getattr(self.model_class, field) == value)

        # 如果没有显式指定 is_deleted 过滤条件，则自动添加
        if self._has_is_deleted_field() and (filters is None or "is_deleted" not in filters):
            query = self._filter_not_deleted(query)

        if order_by is not None:
            query = query.order_by(order_by)

        return query.offset(skip).limit(limit).all()

    def update(
            self,
            db: Session,
            *,
            id: Any,
            obj_in: Dict[str, Any]
    ) -> Optional[T]:
        """
        更新记录，只更新未删除的记录
        
        Args:
            db: 数据库会话
            id: 记录ID
            obj_in: 要更新的字段
            
        Returns:
            Optional[T]: 更新后的记录，如果不存在则返回None
        """
        try:
            db_obj = self.get(db, id)  # 这里会过滤已删除的记录
            if not db_obj:
                return None

            for field, value in obj_in.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            raise e

    def delete(self, db: Session, *, id: Any) -> Optional[T]:
        """
        物理删除记录，只删除未删除的记录
        
        Args:
            db: 数据库会话
            id: 记录ID
            
        Returns:
            Optional[T]: 删除的记录，如果不存在则返回None
        """
        try:
            db_obj = self.get(db, id)  # 这里会过滤已删除的记录
            if not db_obj:
                return None

            db.delete(db_obj)
            db.commit()
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            raise e

    def count(self, db: Session, *, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        计算记录数，排除已删除的记录
        
        Args:
            db: 数据库会话
            filters: 过滤条件
            
        Returns:
            int: 记录数
        """
        query = db.query(self.model_class)

        # 应用过滤条件
        if filters:
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    query = query.filter(getattr(self.model_class, field) == value)

        # 如果没有显式指定 is_deleted 过滤条件，则自动添加
        if self._has_is_deleted_field() and (filters is None or "is_deleted" not in filters):
            query = self._filter_not_deleted(query)

        return query.count()