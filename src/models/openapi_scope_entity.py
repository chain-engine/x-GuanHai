#!/usr/bin/env python3
"""开放 API scope 元数据实体。

启动时自动扫描开放 API 路由的 @app_scope 装饰器，upsert 到本表；
创建 / 编辑应用时从此表拉取可选 scope 列表。
"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infras.database import Base


class OpenApiScopeEntity(Base):
    """开放 API scope 元数据表。"""

    __tablename__ = "openapi_scopes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    scope_code: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Scope 编码，如 rag:read"
    )
    scope_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Scope 中文名")
    module: Mapped[str] = mapped_column(String(50), nullable=False, comment="所属模块")
    operation: Mapped[str] = mapped_column(String(20), nullable=False, comment="操作类型")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="说明")
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="排序序号"
    )
    is_deprecated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0", comment="是否已废弃（路由中不再使用）"
    )
    __table_args__ = (
        Index("uk_scope_code", "scope_code", unique=True),
        Index("idx_module", "module"),
    )


__all__ = ["OpenApiScopeEntity"]
