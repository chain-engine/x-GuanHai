#!/usr/bin/env python3
"""开放 API（面向应用）身份数据实体。

与面向人的账号体系平行：本实体代表"调用方应用/服务"，用 AppId + GuanHai-1
签名鉴权。表结构按 hmac 签名模式设计（本框架不启用明文模式）：
- app_key_hash:      SHA256(app_key)，落库索引快查（预留，当前签名模式不读取）；
- app_key_encrypted: Fernet 加密后的明文 app_key，签名校验时解密重算 HMAC 用；
- auth_mode:         固定 "hmac"，保留字段便于未来灰度扩展。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infras.database import Base


class OpenApiAppEntity(Base):
    """开放 API 应用表。"""

    __tablename__ = "openapi_apps"
    # 主键用 Integer：SQLite 仅 INTEGER PRIMARY KEY 支持自动自增（rowid 别名），
    # BIGINT 主键在 SQLite 下不会自增导致 NOT NULL 失败；MySQL 下 INT AUTO_INCREMENT 等价。
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    # ── 身份标识 ──────────────────────────────────────────
    app_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="对外应用ID，明文，带前缀 gh_live_xxx"
    )
    app_key_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="AppKey 的 SHA256 哈希（明文模式预留，签名模式不读取）"
    )
    app_key_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Fernet 加密的明文 AppKey，HMAC 签名校验时解密用"
    )
    # ── 元信息 ──────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="应用名")
    description: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="", comment="应用描述"
    )
    # ── 授权状态 ──────────────────────────────────────────
    scopes: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        server_default="",
        comment="逗号分隔的权限范围，如 rag:read,document:write",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active", comment="状态：active/disabled"
    )
    auth_mode: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="hmac",
        comment="鉴权模式：hmac（GuanHai-1 签名）",
    )
    # ── 限流 ────────────────────────────────────────────
    rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="60", comment="每分钟限流次数"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近一次成功鉴权时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.current_timestamp(),
    )
    __table_args__ = (Index("uk_app_id", "app_id", unique=True),)


__all__ = ["OpenApiAppEntity"]
