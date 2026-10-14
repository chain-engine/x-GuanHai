#!/usr/bin/env python3
"""MCP 出口的开放接口认证中间件（与 HTTP 同源：AppId + GuanHai-1 签名）。

背景：/mcp 是独立 ASGI 应用（streamable_http_app）挂载在 FastAPI 上，
不经过路由级 Depends / 异常处理器，鉴权必须在中间件层完成。
本中间件与 HTTP 出口（api/open/dependencies.get_current_app）共用同一套原语：
    - 协议计算：core/signature（签名串 / 时间窗 / HMAC 重算）
    - 鉴权编排：services.authenticate_request（会话 / 事务 / Repo 全在 services 层）
    - 请求剥离：utils.openapi.build_auth_context_from_request（HTTP / MCP 共用）

放行规则：
- OPENAPI_ENABLED=False：全部放行（本地无鉴权部署）；
- OPTIONS：放行（CORS 预检请求不携带签名头）；
- 仅 /mcp 前缀的请求执行认证，其余路径交给下游。

操作人透传（审计）：认证通过后将应用身份组装为 operator 上下文，供 MCP 工具
调用 services 时以 operator 参数传入（services 层审计落库）：
    1. contextvar 主通道：中间件与下游 ASGI 应用在同一 asyncio task 内执行，
       MCP 2.x 工具经 anyio.to_thread / 同 task 执行时会捕获该 task 的 context
       快照，工具内可读到当前 operator；
    2. headers 反查兜底：认证结果同时写入 _authed_operators 缓存，工具可经
       ctx.transport.headers 中的 X-App-Id 反查（防御个别调度路径不传播 context）。
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.exceptions import AppException
from src.core.logger import logger
from src.services.gateway_service import authenticate_request
from src.utils.openapi import build_auth_context_from_request

# ── 操作人上下文（MCP 工具层读取）────────────────────────────
# contextvar 主通道：认证中间件设置，同 task 的工具执行可读。
current_mcp_operator: ContextVar[dict[str, Any] | None] = ContextVar(
    "mcp_operator", default=None
)
# headers 反查兜底缓存：app_id → operator（认证通过时写入，工具经 X-App-Id 反查）。
_authed_operators: dict[str, dict[str, Any]] = {}


def get_current_operator() -> dict[str, Any] | None:
    """读取当前 MCP 请求的操作人上下文（工具函数内调用）。"""
    return current_mcp_operator.get()


def resolve_operator(app_id: str | None) -> dict[str, Any] | None:
    """按 AppId 反查认证缓存中的操作人上下文（headers 反查兜底通道）。"""
    if not app_id:
        return None
    return _authed_operators.get(app_id)


class OpenApiAuthMiddleware:
    """MCP 出口开放接口认证中间件（纯 ASGI，读取 body 后原样放回下游）。

    用法（组装根，先于服务启动注册）：
        app.add_middleware(OpenApiAuthMiddleware)
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        """ASGI 入口：仅对 /mcp 的 POST 请求执行 AppId + 签名认证。"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # 未启用开放接口认证 / 非 MCP 路径 / CORS 预检：直接放行
        if not settings.OPENAPI_ENABLED or not path.startswith("/mcp") or method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # 读取请求体（签名串 SHA256 计算需要原始 body），随后原样放回下游
        body = await _read_body(receive)
        request = Request(scope)

        try:
            ctx = build_auth_context_from_request(request, body)
            current_app = await authenticate_request(ctx)
        except AppException as exc:
            logger.warning(f"MCP auth rejected: {exc.message}")
            response = JSONResponse(
                status_code=exc.code,
                content={"code": exc.code, "message": exc.message},
            )
            await response(scope, receive, send)
            return

        # 认证通过：组装操作人上下文（审计用），contextvar 主通道 + 缓存兜底
        operator = {
            "operator_id": current_app.app_id,
            "operator_name": current_app.name,
            "ip_address": _client_ip(scope),
        }
        current_mcp_operator.set(operator)
        _authed_operators[current_app.app_id] = operator

        # 恢复 body 流并转发下游 MCP 应用。
        # 注意：只能注入一次 http.request（body），后续 receive 必须继续走原始
        # receive 通道——MCP 2.x 的 SSE 响应阶段会再次调用 receive() 等待客户端
        # 断开/新消息，若重复返回 http.request 会触发
        # "Unexpected message received: http.request"。
        sent_body = False

        async def receive_with_body():
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, receive_with_body, send)


async def _read_body(receive) -> bytes:
    """读取 ASGI 请求体（支持分片，异常断开时返回已读部分）。"""
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _client_ip(scope: dict[str, Any]) -> str | None:
    """从 ASGI scope 取客户端 IP（兼容反向代理透传 X-Forwarded-For 与直连地址）。"""
    headers = {k.decode().lower(): v.decode() for k, v in (scope.get("headers") or [])}
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else None


__all__ = ["OpenApiAuthMiddleware", "get_current_operator", "resolve_operator"]
