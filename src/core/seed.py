#!/usr/bin/env python3
"""种子数据管理模块。

应用启动时创建系统内置种子数据：
    默认管理应用（openapi_apps 表，固定保留 app_id="app"，默认凭据 gk_admin_change_me）。
已存在则跳过，保证幂等，可重复调用。

本模块自持会话、直接读写数据表，不依赖 services 层：

Functions:
    init_seed_data: 初始化种子数据（幂等）
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core.logger import logger
from src.infras.database import get_session
from src.models.openapi_app_entity import OpenApiAppEntity
from src.utils import security
from src.utils.openapi import validate_scopes

# ── 种子默认应用凭据 ──────────────────────────────────────────
# app_id 为固定保留值，作为种子幂等键：已存在即跳过；多 worker 并发
# 首启时依赖 uk_app_id 唯一索引兜底，仅允许创建一次。
# app_key 为公开默认值，生产环境应在首启后立即重置或吊销该应用。
SEED_ADMIN_APP_ID = "app"
SEED_ADMIN_APP_KEY = "gk_admin_change_me"
SEED_ADMIN_SCOPES = ["admin", "rag:read", "document:read", "document:write"]


def init_seed_data() -> None:
    """初始化种子数据（幂等，可重复调用）。

    默认管理应用：openapi_apps 无默认管理应用（app_id="app"）时按固定默认凭据
    创建，解决"先有鸡还是先有蛋"——首个管理应用不经过 HTTP 管理接口。
    scope 归属按常量目录 OpenApiScopeCode 校验（不读取 openapi_scopes 表），
    故无需先对账 scope 目录；事务在本函数内直接管理。
    多 worker 并发首启时依赖 uk_app_id 唯一索引兜底，冲突方视为已种子化。
    """
    session = get_session()
    try:
        existing = session.execute(
            select(OpenApiAppEntity).where(OpenApiAppEntity.app_id == SEED_ADMIN_APP_ID)
        ).scalars().first()
        if existing is not None:
            return
        # 启动即校验，scope 目录漂移时在启动期立即暴露，而非等到网关鉴权失败
        validate_scopes(SEED_ADMIN_SCOPES)
        session.add(
            OpenApiAppEntity(
                app_id=SEED_ADMIN_APP_ID,
                app_key_hash=security.sha256_hex(SEED_ADMIN_APP_KEY),
                app_key_encrypted=security.encrypt_text(SEED_ADMIN_APP_KEY),
                name="app",
                description="启动种子自动创建的默认管理应用（默认凭据，生产环境请立即重置或吊销）",
                scopes=",".join(SEED_ADMIN_SCOPES),
            )
        )
        session.commit()
        logger.info(
            "OpenAPI seed admin app created: "
            f"app_id={SEED_ADMIN_APP_ID} app_key={SEED_ADMIN_APP_KEY} "
            "(默认凭据，生产环境请立即重置或吊销)"
        )
    except IntegrityError:
        # 并发首启时其他 worker 已创建，本次空跑
        session.rollback()
        logger.debug("OpenAPI seed admin app already exists, skipped")
    finally:
        session.close()


__all__ = ["init_seed_data"]
