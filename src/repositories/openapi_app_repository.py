#!/usr/bin/env python3
"""开放 API 应用数据访问（openapi_apps / openapi_scopes 两张表）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.exceptions import ConflictError
from src.models.openapi_app_entity import OpenApiAppEntity
from src.models.openapi_scope_entity import OpenApiScopeEntity


class OpenApiAppRepository:
    """OpenApiApp 数据访问（管理面写、网关面读，共用同一实现）。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── 查询 ──────────────────────────────────────────────
    def get_by_app_id(self, app_id: str) -> OpenApiAppEntity | None:
        """按对外 AppId 查询。"""
        return self._session.execute(
            select(OpenApiAppEntity).where(OpenApiAppEntity.app_id == app_id)
        ).scalars().first()

    def get_by_id(self, entity_id: int) -> OpenApiAppEntity | None:
        """按主键查询。"""
        return self._session.get(OpenApiAppEntity, entity_id)

    def list_apps(
        self,
        keyword: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[OpenApiAppEntity], int]:
        """按名称关键字分页查询应用（主键升序保证分页稳定）。

        Returns:
            (当前页实体列表, 匹配总数)
        """
        base = select(OpenApiAppEntity)
        if keyword:
            base = base.where(OpenApiAppEntity.name.like(f"%{keyword}%"))
        total = self._session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
        stmt = base.order_by(OpenApiAppEntity.id).offset(skip).limit(limit)
        return list(self._session.execute(stmt).scalars().all()), total

    def count(self) -> int:
        """应用总数（bootstrap 判断首启用）。"""
        return self._session.execute(
            select(func.count()).select_from(OpenApiAppEntity)
        ).scalar_one()

    def list_active_scopes(self) -> list[OpenApiScopeEntity]:
        """查询全部未废弃的 scope（按排序号与主键升序）。"""
        stmt = (
            select(OpenApiScopeEntity)
            .where(OpenApiScopeEntity.is_deprecated.is_(False))
            .order_by(OpenApiScopeEntity.sort_order, OpenApiScopeEntity.id)
        )
        return list(self._session.execute(stmt).scalars().all())

    # ── 写入 ──────────────────────────────────────────────
    def create(
        self,
        *,
        app_id: str,
        app_key_hash: str,
        app_key_encrypted: str | None,
        name: str,
        description: str,
        scopes: str,
        auth_mode: str = "hmac",
        rate_limit_per_minute: int = 60,
        status: str = "active",
    ) -> OpenApiAppEntity:
        """创建应用（app_id 唯一冲突时抛 ConflictError）。"""
        entity = OpenApiAppEntity(
            app_id=app_id,
            app_key_hash=app_key_hash,
            app_key_encrypted=app_key_encrypted,
            name=name,
            description=description,
            scopes=scopes,
            auth_mode=auth_mode,
            rate_limit_per_minute=rate_limit_per_minute,
            status=status,
        )
        try:
            self._session.add(entity)
            self._session.flush()
        except IntegrityError as e:
            self._session.rollback()
            raise ConflictError(message=f"AppId 已存在: {app_id}") from e
        return entity

    def update_status(self, app_id: str, status: str) -> bool:
        """更新应用启用状态（revoke → disabled / enable → active）。

        Returns:
            bool: 是否存在并已更新
        """
        entity = self.get_by_app_id(app_id)
        if entity is None:
            return False
        entity.status = status
        self._session.flush()
        return True

    def delete(self, app_id: str) -> bool:
        """物理删除应用（吊销的常规路径是置 disabled，删除用于清理）。"""
        entity = self.get_by_app_id(app_id)
        if entity is None:
            return False
        self._session.delete(entity)
        self._session.flush()
        return True

    def touch_last_used(self, app_id: str) -> None:
        """更新最近鉴权时间（失败不影响主流程）。"""
        try:
            entity = self.get_by_app_id(app_id)
            if entity is not None:
                entity.last_used_at = datetime.now()
                self._session.flush()
        except Exception:
            self._session.rollback()


__all__ = ["OpenApiAppRepository"]
