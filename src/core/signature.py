#!/usr/bin/env python3
"""GuanHai-1 开放接口签名 / 解签工具（协议层纯函数，无 FastAPI / DB 依赖）。

服务端与调用方共用同一协议（与 examples/openapi_client.py、集成文档严格对齐）：
    签名串 = Ver + METHOD + URI + Content-Type + Date + SHA256(body)
    签名值 = HMAC-SHA256(AppKey, 签名串)

约定细节：
    - URI：完整路径 + 查询串（不含域名）；**path 统一去除尾部斜杠后参与
      签名**（/mcp 与 /mcp/ 视为同一资源，服务端剥离与调用方签名同源归一），
      必须包含 /api/v1 或 /mcp 前缀；
    - Content-Type：固定 application/json，与请求是否携带 body 无关；
    - Date：RFC1123 GMT 格式，经 X-App-Date 请求头传递；
    - body 为空时，SHA256(body) 部分取空字符串。

本模块只做协议计算；应用查询 / 密钥解密由网关服务
（src/services/gateway_service.py）负责；HTTP 头 / 请求体剥离由
接入层（HTTP：src/api/open/dependencies.py；MCP：src/mcp_server/auth.py）
经 src/utils/openapi.build_auth_context_from_request 统一完成。
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from src.constants import (
    OPENAPI_ALGORITHM,
    OPENAPI_SIGNATURE_WINDOW_SECONDS,
)
from src.utils.security import constant_time_equals, hmac_sha256_hex, sha256_hex


def parse_http_date(date_str: str) -> datetime | None:
    """解析 RFC1123 / RFC850 / asctime 格式的 HTTP 日期，返回 UTC datetime。

    解析失败返回 None（由调用方按"时间窗非法"处理）。
    """
    try:
        dt = parsedate_to_datetime(date_str)
    except (TypeError, ValueError, OverflowError):
        return None
    if dt is None:
        return None
    return dt.astimezone(UTC)


def build_signing_string(
    *,
    method: str,
    uri: str,
    content_type: str,
    date: str,
    body: bytes,
) -> str:
    """构造 GuanHai-1 待签名串（与外部调用方的协议约定，勿随意改）。

    格式：Ver + METHOD + URI + Content-Type + Date + SHA256(body)，直接拼接无分隔符。
    Content-Type 固定为 application/json（与请求是否携带 body 无关），
    GET 无 body 时同样拼接该固定值，body 为空则 SHA256(body) 取空字符串。
    """
    body_hash = sha256_hex(body.decode("utf-8")) if body else ""
    return "".join(
        [
            OPENAPI_ALGORITHM,
            method.upper(),
            uri,
            content_type,
            date,
            body_hash,
        ]
    )


def sign(
    *,
    app_key: str,
    method: str,
    uri: str,
    content_type: str,
    date: str,
    body: bytes,
) -> str:
    """HMAC-SHA256 签名（开放接口调用方侧逻辑，供测试 / 对接参考）。

    与 examples/openapi_client.py 的签名实现等价：
        hmac.new(app_key, signing_string, hashlib.sha256).hexdigest()
    """
    return hmac_sha256_hex(
        app_key,
        build_signing_string(method=method, uri=uri, content_type=content_type, date=date, body=body),
    )


def verify_signature(
    *,
    app_key: str,
    method: str,
    uri: str,
    content_type: str,
    date: str,
    body: bytes,
    signature: str,
) -> bool:
    """解签校验：以 AppKey 重算签名并与调用方签名常量时间比对。

    参数与 build_signing_string / sign 完全同源，调用方务必传入与
    请求头 X-App-Date / 原始 body 一致的值，否则校验必然失败。
    """
    expected = sign(app_key=app_key, method=method, uri=uri, content_type=content_type, date=date, body=body)
    return constant_time_equals(expected, signature)


def is_request_date_valid(
    date_str: str,
    *,
    window_seconds: int = OPENAPI_SIGNATURE_WINDOW_SECONDS,
) -> bool:
    """校验 X-App-Date 是否落在当前时间窗内（防重放）。

    时间窗绝对值超出 window_seconds 即判定失效；日期格式非法同样返回 False。
    """
    request_time = parse_http_date(date_str)
    if request_time is None:
        return False
    now = datetime.now(UTC)
    return abs((now - request_time).total_seconds()) <= window_seconds


__all__ = [
    "parse_http_date",
    "build_signing_string",
    "sign",
    "verify_signature",
    "is_request_date_valid",
]
