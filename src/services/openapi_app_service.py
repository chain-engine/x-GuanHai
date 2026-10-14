#!/usr/bin/env python3
"""开放 API 应用管理业务逻辑（管理面 / CLI 共用）。

- create_app：生成 AppId + AppKey，落库仅存 SHA256 哈希与 Fernet 密文，
  明文 AppKey 只在创建响应中出现一次；
- list_apps / revoke_app / enable_app / delete_app：应用生命周期管理。

启动种子（默认管理应用）与 scope 目录对账不在此层：分别由 core.seed.init_seed_data
与 http_server.scope_decorator.sync_scopes_to_db 自持会话直接完成。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.core.exceptions import NotFoundError
from src.repositories.openapi_app_repository import OpenApiAppRepository
from src.schemas.openapi_app import (
    OpenApiAppCreateRequest,
    OpenApiAppCreateResponse,
    OpenApiAppItem,
    OpenApiAppListResponse,
)
from src.services.audit_service import AuditService
from src.utils import security
from src.utils.openapi import generate_app_id, parse_scopes, validate_scopes


class OpenApiAppService:
    """开放 API 应用管理服务（创建 / 列表 / 吊销 / 启停）。"""

    entity_type = "openapi_app"

    def __init__(
        self,
        repo: OpenApiAppRepository,
        audit_service: AuditService | None = None,
    ) -> None:
        self._repository = repo
        self._audit_service = audit_service

    def _audit(
        self,
        entity_id: str | None,
        action: str,
        operator: dict[str, Any] | None = None,
        before_data: dict[str, Any] | None = None,
        after_data: dict[str, Any] | None = None,
        remarks: str | None = None,
    ) -> None:
        """记录开放 API 应用管理审计（审计失败不阻断业务）。"""
        if self._audit_service is None:
            return
        self._audit_service.log_event(
            entity_type=self.entity_type,
            entity_id=entity_id,
            action=action,
            operator=operator,
            before_data=before_data,
            after_data=after_data,
            remarks=remarks,
        )

    def create_app(
        self,
        request: OpenApiAppCreateRequest,
        operator: dict[str, Any] | None = None,
    ) -> OpenApiAppCreateResponse:
        """创建开放 API 应用。

        Args:
            request: 应用名 / 描述 / scope 列表 / 限流

        Returns:
            OpenApiAppCreateResponse: 含明文 AppKey（仅此一次）
        """
        validate_scopes(request.scopes)
        app_id = generate_app_id()
        app_key = security.generate_app_key()

        entity = self._repository.create(
            app_id=app_id,
            app_key_hash=security.sha256_hex(app_key),
            app_key_encrypted=security.encrypt_text(app_key),
            name=request.name,
            description=request.description,
            scopes=",".join(request.scopes),
            rate_limit_per_minute=request.rate_limit_per_minute,
        )
        # 业务审计：创建应用（after 不含 AppKey 明文，密钥仅出现在一次性的创建响应中）
        self._audit(
            entity_id=entity.app_id,
            action="create",
            operator=operator,
            after_data={
                "name": entity.name,
                "description": entity.description,
                "scopes": request.scopes,
                "auth_mode": entity.auth_mode or "hmac",
                "rate_limit_per_minute": entity.rate_limit_per_minute,
                "status": entity.status,
            },
            remarks=f"创建开放 API 应用「{request.name}」",
        )
        return OpenApiAppCreateResponse(
            app_id=entity.app_id,
            app_key=app_key,
            name=entity.name,
            scopes=parse_scopes(entity.scopes),
            auth_mode=entity.auth_mode or "hmac",
            rate_limit_per_minute=entity.rate_limit_per_minute,
        )

    def list_apps(
        self,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
        operator: dict[str, Any] | None = None,
    ) -> OpenApiAppListResponse:
        """分页列出应用（不返回任何密钥信息）。

        Args:
            keyword: 按名称关键字过滤
            page: 页码
            page_size: 每页数量
            operator: 操作人上下文（读审计用，由 api 层传入；系统内部调用可不传）
        """
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        entities, total = self._repository.list_apps(
            keyword=keyword,
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        items = [
            OpenApiAppItem(
                app_id=e.app_id,
                name=e.name,
                description=e.description,
                scopes=parse_scopes(e.scopes),
                status=e.status,
                auth_mode=e.auth_mode or "hmac",
                rate_limit_per_minute=e.rate_limit_per_minute,
                last_used_at=e.last_used_at,
                created_at=e.created_at,
            )
            for e in entities
        ]
        # 业务审计：应用列表读取（after 记筛选条件与总数，不记密钥与明细）
        self._audit(
            entity_id=None,
            action="list",
            operator=operator,
            after_data={"keyword": keyword, "page": page, "page_size": page_size, "total": total},
            remarks="查询开放 API 应用列表",
        )
        return OpenApiAppListResponse(total=total, page=page, page_size=page_size, items=items)

    def revoke_app(
        self,
        app_id: str,
        operator: dict[str, Any] | None = None,
    ) -> OpenApiAppItem:
        """吊销应用（status → disabled，即时生效；不删除记录）。"""
        if not self._repository.update_status(app_id, "disabled"):
            raise NotFoundError(message=f"应用不存在: {app_id}")
        item = self._require_app(app_id)
        # 业务审计：吊销应用
        self._audit(
            entity_id=app_id,
            action="revoke",
            operator=operator,
            before_data={"status": "active"},
            after_data={"status": "disabled", "name": item.name},
            remarks=f"吊销应用「{item.name}」",
        )
        return item

    def enable_app(
        self,
        app_id: str,
        operator: dict[str, Any] | None = None,
    ) -> OpenApiAppItem:
        """重新启用应用（status → active）。"""
        if not self._repository.update_status(app_id, "active"):
            raise NotFoundError(message=f"应用不存在: {app_id}")
        item = self._require_app(app_id)
        # 业务审计：启用应用
        self._audit(
            entity_id=app_id,
            action="enable",
            operator=operator,
            before_data={"status": "disabled"},
            after_data={"status": "active", "name": item.name},
            remarks=f"启用应用「{item.name}」",
        )
        return item

    def delete_app(
        self,
        app_id: str,
        operator: dict[str, Any] | None = None,
    ) -> None:
        """物理删除应用（清理用途；常规吊销请用 revoke_app）。"""
        # 删除前快照（审计 before_data）
        entity = self._repository.get_by_app_id(app_id)
        if entity is None:
            raise NotFoundError(message=f"应用不存在: {app_id}")
        before_data = {
            "name": entity.name,
            "status": entity.status,
            "scopes": parse_scopes(entity.scopes),
        }
        self._repository.delete(app_id)
        # 业务审计：删除应用
        self._audit(
            entity_id=app_id,
            action="delete",
            operator=operator,
            before_data=before_data,
            after_data={"status": "deleted"},
            remarks=f"删除应用「{before_data['name']}」",
        )

    def _require_app(self, app_id: str) -> OpenApiAppItem:
        """按 app_id 组装 OpenApiAppItem（不存在抛 NotFoundError）。"""
        entity = self._repository.get_by_app_id(app_id)
        if entity is None:
            raise NotFoundError(message=f"应用不存在: {app_id}")
        return OpenApiAppItem(
            app_id=entity.app_id,
            name=entity.name,
            description=entity.description,
            scopes=parse_scopes(entity.scopes),
            status=entity.status,
            auth_mode=entity.auth_mode or "hmac",
            rate_limit_per_minute=entity.rate_limit_per_minute,
            last_used_at=entity.last_used_at,
            created_at=entity.created_at,
        )


def build_openapi_app_service(
    session: Session,
    audit_service: AuditService | None = None,
) -> OpenApiAppService:
    """构建开放 API 应用管理服务（组装 Repo；供 API 依赖工厂复用）。

    Repo 实例化收敛在 services 层，api 层只声明依赖、不直接接触数据访问层。
    """
    return OpenApiAppService(
        repo=OpenApiAppRepository(session=session),
        audit_service=audit_service,
    )


__all__ = ["OpenApiAppService", "build_openapi_app_service"]
