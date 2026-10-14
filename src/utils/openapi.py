#!/usr/bin/env python3
"""开放 API 通用工具——应用身份 / scope 目录 / 请求上下文剥离的公共协议函数。

从服务层抽出的公共片段：创建 App / 解析 scopes / 校验 scopes /
从请求剥离鉴权上下文全部经由此处，保证 HTTP 与 MCP 双出口口径一致。
"""

from __future__ import annotations

import secrets

from fastapi import Request

from src.constants import OPENAPI_HEADER_APP_ID, OPENAPI_HEADER_AUTHORIZATION, OPENAPI_HEADER_DATE
from src.constants.scopes import OpenApiScopeCode
from src.core.exceptions import ValidationError
from src.schemas.openapi_app import OpenApiAuthContext


def generate_app_id() -> str:
    """生成对外 AppId。

    前缀 = 项目缩写 gh + 环境标识：gh_live_xxxxxxxx / gh_test_xxxxxxxx
    （生产/其他环境按 OPENAPI_ENV 语义简化：固定 gh_ 前缀 + 16 字节随机
    32 hex 字符，约 128bit 熵，抗枚举）。
    """
    return f"gh_{secrets.token_hex(16)}"


def parse_scopes(scopes: str | None) -> list[str]:
    """库中逗号分隔的 scopes 字段 → list[str]，去空。"""
    if not scopes:
        return []
    return [s.strip() for s in scopes.split(",") if s.strip()]


def validate_scopes(scopes: list[str]) -> None:
    """校验 scope 列表必须全部在合法目录（OpenApiScopeCode 枚举）内。

    写入 openapi_apps.scopes 前必须调用：scope 为有限固定目录，
    不在目录内的值（拼写错误、已下线 scope）永远无法通过网关鉴权。

    Args:
        scopes: 待校验的 scope 编码列表

    Raises:
        ValidationError: 存在不在目录内的 scope 时抛出，错误信息列出全部非法值
    """
    if not scopes:
        return
    valid_marks = {scope.mark for scope in OpenApiScopeCode}
    invalid = sorted({s for s in scopes if s not in valid_marks})
    if invalid:
        raise ValidationError(
            message=f"存在非法的权限范围: {', '.join(invalid)}",
            detail={"invalid_scopes": invalid, "valid_scopes": sorted(valid_marks)},
        )


def build_auth_context_from_request(request: Request, body: bytes) -> OpenApiAuthContext:
    """从 ASGI/FastAPI Request 剥离开放接口鉴权上下文（HTTP / MCP 接入层共用）。

    集中剥离 X-App-Id / X-App-Date / X-App-Authorization 请求头、HTTP 方法、
    URI（path + raw query）与请求体，使 services 层只接收纯数据
    （OpenApiAuthContext），不依赖 Web 框架对象。

    URI 归一约定（GuanHai-1 协议）：path 去除尾部斜杠后参与签名。
    例如 MCP 端点 /mcp 与 /mcp/ 视为同一资源（服务端 307 重定向场景），
    调用方与服务端必须使用同一归一结果，否则签名必然不匹配。

    Args:
        request: FastAPI Request（HTTP 路由或 MCP 中间件均可）
        body: 已读取的请求体字节流（签名串 SHA256 计算需要原始 body）

    Returns:
        OpenApiAuthContext: 鉴权上下文纯数据
    """
    path = request.url.path.rstrip("/") or "/"
    uri = path
    if request.url.query:
        uri += f"?{request.url.query}"
    return OpenApiAuthContext(
        app_id=request.headers.get(OPENAPI_HEADER_APP_ID, ""),
        authorization=request.headers.get(OPENAPI_HEADER_AUTHORIZATION),
        date=request.headers.get(OPENAPI_HEADER_DATE),
        method=request.method,
        uri=uri,
        body=body,
    )


__all__ = ["generate_app_id", "parse_scopes", "validate_scopes", "build_auth_context_from_request"]
