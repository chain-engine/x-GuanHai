#!/usr/bin/env python3
"""开放 API（网关 / 管理面）DTO。

- OpenApiCurrentApp：鉴权通过后注入请求上下文的调用方应用身份（机器身份）；
- OpenApiAuthContext：接入层剥离请求后的鉴权上下文纯数据；
- OpenApiAppCreateRequest / OpenApiAppCreateResponse：管理面创建应用（明文 Key 仅返回一次）；
- OpenApiAppItem / OpenApiAppListResponse：管理面列表。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OpenApiCurrentApp(BaseModel):
    """当前调用方应用（机器身份，无终端用户上下文）。"""

    app_id: str = Field(description="应用ID")
    name: str = Field(description="应用名")
    scopes: list[str] = Field(default_factory=list, description="已授权 scope 列表")
    auth_mode: str = Field(default="hmac", description="鉴权模式")
    rate_limit_per_minute: int = Field(default=60, description="每分钟限流次数")


class OpenApiAuthContext(BaseModel):
    """开放接口单次请求的鉴权上下文（纯数据，无框架依赖）。

    由接入层（HTTP：http_server/dependencies.get_current_app；MCP：mcp_server/auth.py）
    通过 utils.openapi.build_auth_context_from_request 从请求剥离为纯数据后，
    统一交给 services.authenticate_request 鉴权：
    - HTTP 方法 / URI / 请求体：签名串重算所需；
    - X-App-Id / X-App-Date / X-App-Authorization：鉴权凭证。
    """

    app_id: str = Field(description="X-App-Id：应用标识")
    authorization: str | None = Field(
        default=None,
        description="X-App-Authorization：GuanHai-1 签名，格式 'GuanHai-1 {app_id}:{signature}'",
    )
    date: str | None = Field(
        default=None, description="X-App-Date：RFC1123 GMT 时间（签名时间窗校验）"
    )
    method: str = Field(description="HTTP 方法（GET/POST/PUT/PATCH/DELETE）")
    uri: str = Field(description="完整路径 + 查询串（不含域名，含 /api/v1 前缀）")
    body: bytes = Field(default=b"", description="请求体字节流（参与签名串 SHA256 计算）")


class OpenApiAppCreateRequest(BaseModel):
    """创建开放 API 应用请求（管理面 / CLI）。"""

    name: str = Field(..., min_length=1, max_length=100, description="应用名")
    description: str = Field(default="", max_length=255, description="应用描述")
    scopes: list[str] = Field(..., description="授权 scope 列表，如 ['rag:read']")
    rate_limit_per_minute: int = Field(default=60, ge=1, le=100000, description="每分钟限流次数")


class OpenApiAppCreateResponse(BaseModel):
    """创建结果（AppKey 明文仅在此响应中出现一次，之后只能重置/吊销）。"""

    app_id: str = Field(description="应用ID")
    app_key: str = Field(description="AppKey 明文（仅此一次，请立即保存）")
    name: str = Field(description="应用名")
    scopes: list[str] = Field(default_factory=list, description="已授权 scope 列表")
    auth_mode: str = Field(default="hmac", description="鉴权模式")
    rate_limit_per_minute: int = Field(default=60, description="每分钟限流次数")


class OpenApiAppItem(BaseModel):
    """应用列表项（不包含任何密钥信息）。"""

    app_id: str = Field(description="应用ID")
    name: str = Field(description="应用名")
    description: str = Field(default="", description="应用描述")
    scopes: list[str] = Field(default_factory=list, description="已授权 scope 列表")
    status: str = Field(description="状态：active/disabled")
    auth_mode: str = Field(default="hmac", description="鉴权模式")
    rate_limit_per_minute: int = Field(default=60, description="每分钟限流次数")
    last_used_at: datetime | None = Field(default=None, description="最近一次成功鉴权时间")
    created_at: datetime | None = Field(default=None, description="创建时间")


class OpenApiAppListResponse(BaseModel):
    """应用分页列表。"""

    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页记录数")
    items: list[OpenApiAppItem] = Field(default_factory=list, description="应用列表")


__all__ = [
    "OpenApiCurrentApp",
    "OpenApiAuthContext",
    "OpenApiAppCreateRequest",
    "OpenApiAppCreateResponse",
    "OpenApiAppItem",
    "OpenApiAppListResponse",
]
