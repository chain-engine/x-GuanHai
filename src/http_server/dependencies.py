#!/usr/bin/env python3
"""HTTP 接入层统一依赖管理模块。

承载 HTTP 接入层（http_server/）的全部依赖注入：
- 业务服务依赖：get_rag_service / get_document_service（从 app.state 取，避免重复初始化）
- 开放 API 鉴权域依赖：请求头解析（X-App-Id / X-App-Date / X-App-Authorization）、
  网关鉴权（get_current_app）与 scope 门槛（require_app_scope）
- 应用态操作人上下文（get_app_operator_context，供审计 / 日志使用）

当 settings.OPENAPI_ENABLED=False（本地开发 / 无鉴权部署）时，
鉴权依赖自动放行（返回 internal 应用），保证不破坏既有本地调用。

各 v1 路由模块一律从本模块导入依赖，不在路由文件内再定义。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.constants import (
    OPENAPI_HEADER_APP_ID,
    OPENAPI_HEADER_AUTHORIZATION,
    OPENAPI_HEADER_DATE,
)
from src.constants.scopes import OpenApiScopeCode
from src.core.config import settings
from src.core.exceptions import ForbiddenError
from src.infras.database import get_db_session
from src.schemas.openapi_app import OpenApiCurrentApp
from src.services.audit_service import AuditService
from src.services.document_service import DocumentService
from src.services.gateway_service import authenticate_request
from src.services.openapi_app_service import OpenApiAppService, build_openapi_app_service
from src.services.rag_service import RAGService
from src.utils.openapi import build_auth_context_from_request

# 开放 API 认证方案（Swagger UI 右上角会出现 Authorize 按钮）
_app_id_scheme = APIKeyHeader(name=OPENAPI_HEADER_APP_ID, scheme_name="OpenAppId", auto_error=False)
_app_date_scheme = APIKeyHeader(name=OPENAPI_HEADER_DATE, scheme_name="OpenAppDate", auto_error=False)
_app_auth_scheme = APIKeyHeader(
    name=OPENAPI_HEADER_AUTHORIZATION, scheme_name="OpenAppAuthorization", auto_error=False
)


def get_rag_service(request: Request) -> RAGService:
    """依赖注入：获取 RAG 服务（应用启动时初始化的共享实例）"""
    return request.app.state.rag_service


def get_document_service(request: Request) -> DocumentService:
    """依赖注入：获取文档服务（应用启动时初始化的共享实例）"""
    return request.app.state.document_service


def get_audit_service(request: Request) -> AuditService:
    """依赖注入：获取审计日志服务（无状态共享实例）。"""
    return request.app.state.audit_service


def get_openapi_app_service(
    db_session: Session = Depends(get_db_session),
    audit_service: AuditService = Depends(get_audit_service),
) -> OpenApiAppService:
    """获取开放 API 应用管理服务（管理面）。

    api 层仅声明依赖并传递会话，不直接接触数据访问层。
    """
    return build_openapi_app_service(db_session, audit_service=audit_service)


def get_app_operator_context(app: OpenApiCurrentApp, request: Request | None = None) -> dict[str, Any]:
    """构造应用态操作人上下文（供写操作审计 / 日志使用）。"""
    client_ip = None
    if request is not None:
        # 优先取反向代理透传的真实 IP，回退到直连地址
        forwarded = request.headers.get("X-Forwarded-For")
        client_ip = (forwarded.split(",")[0].strip() if forwarded else None) or (
            request.client.host if request.client else None
        )
    return {
        "operator_id": app.app_id,
        "operator_name": app.name,
        "ip_address": client_ip,
    }


def _internal_app() -> OpenApiCurrentApp:
    """无鉴权部署（OPENAPI_ENABLED=False）时的内部放行应用。"""
    return OpenApiCurrentApp(
        app_id="internal",
        name="internal",
        scopes=[scope.mark for scope in OpenApiScopeCode],
        auth_mode="internal",
        rate_limit_per_minute=0,
    )


async def get_current_app(
    request: Request,
    _app_id: str | None = Depends(_app_id_scheme),
    _app_date: str | None = Depends(_app_date_scheme),
    _app_auth: str | None = Depends(_app_auth_scheme),
) -> OpenApiCurrentApp:
    """解析开放接口应用身份（HTTP 出口）。

    在 API 层把 FastAPI Request 剥离为 OpenApiAuthContext 纯数据后，
    委托 services.authenticate_request 完成鉴权（会话 / 事务在 services 层），
    与 MCP 出口（src/mcp_server/auth.py）共用同一套原语。
    """
    if not settings.OPENAPI_ENABLED:
        return _internal_app()
    body = b""
    try:
        body = await request.body()
    except Exception:
        body = b""
    ctx = build_auth_context_from_request(request, body)
    current = await authenticate_request(ctx)
    request.state.current_app = current
    return current


def require_app_scope(scope: str) -> Callable[..., OpenApiCurrentApp]:
    """要求当前应用必须拥有指定 scope。

    Args:
        scope: 目标 scope 编码

    Returns:
        依赖项函数，校验通过后返回当前应用
    """

    def dependency(app: OpenApiCurrentApp = Depends(get_current_app)) -> OpenApiCurrentApp:
        if not settings.OPENAPI_ENABLED:
            return app
        if scope not in app.scopes:
            raise ForbiddenError(message=f"应用缺少 scope: {scope}")
        return app

    return dependency


__all__ = [
    "get_rag_service",
    "get_document_service",
    "get_openapi_app_service",
    "get_audit_service",
    "get_current_app",
    "require_app_scope",
    "get_app_operator_context",
]
