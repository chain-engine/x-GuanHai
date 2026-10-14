#!/usr/bin/env python3
"""x-GuanHai 开放 API GuanHai-1 签名调用示例客户端（演示 / 对接参考）。

签名协议（与服务端 src/core/signature.py 严格对齐）：
    签名串 = GuanHai-1 + METHOD + URI + Content-Type + Date + SHA256(body)
    - URI：完整路径 + 查询串（不含域名），必须包含 /api/v1 前缀；
    - Content-Type：固定 application/json，与请求是否携带 body 无关；
    - Date：RFC1123 GMT 格式，经 X-App-Date 请求头传递；
    - body 为空时，SHA256(body) 部分取空字符串。

使用方式：
    python examples/openapi_client.py --app-id gh_xxx --app-key gk_xxx
        [--base-url http://127.0.0.1:8000] [--timeout 10] [--verbose] [--with-post]

环境变量：
    OPENAPI_APP_ID / OPENAPI_APP_KEY / OPENAPI_BASE_URL / OPENAPI_TIMEOUT / OPENAPI_VERBOSE

前提：
    1. 后端服务已启动（默认 http://127.0.0.1:8000）；
    2. 已通过管理面（CLI 或 /api/v1/apps）创建开放应用并取得 AppId / AppKey；
    3. 应用已授权所需 scope（--with-post 演示需要 document:write）。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass
from email.utils import formatdate
from typing import Any, Final
from urllib.parse import urlparse

import requests

# ── 协议常量（与服务端 src/constants/constants.py 保持一致，禁止单独修改）──
ALGORITHM: Final[str] = "GuanHai-1"  # 签名算法版本号（Ver）
SIGN_CONTENT_TYPE: Final[str] = "application/json"  # 签名串中 Content-Type 固定值
API_BASE_PATH: Final[str] = "/api/v1"  # 签名串使用的 URI 前缀（含版本号）
DEFAULT_BASE_URL: Final[str] = f"http://127.0.0.1:8000{API_BASE_PATH}"
DEFAULT_TIMEOUT: Final[float] = 10.0

# ── 凭证注入环境变量名 ────────────────────────────────
ENV_APP_ID: Final[str] = "OPENAPI_APP_ID"
ENV_APP_KEY: Final[str] = "OPENAPI_APP_KEY"
ENV_BASE_URL: Final[str] = "OPENAPI_BASE_URL"
ENV_TIMEOUT: Final[str] = "OPENAPI_TIMEOUT"
ENV_VERBOSE: Final[str] = "OPENAPI_VERBOSE"


@dataclass
class ClientConfig:
    app_id: str
    app_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    verbose: bool = False


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


def load_config(args: argparse.Namespace) -> ClientConfig:
    """凭证注入优先级：命令行参数 > 环境变量 > 报错。"""
    app_id = args.app_id or os.environ.get(ENV_APP_ID, "")
    app_key = args.app_key or os.environ.get(ENV_APP_KEY, "")
    if not app_id or not app_key:
        print(
            "错误：缺少 AppId / AppKey。请通过 --app-id/--app-key 参数或 "
            f"{ENV_APP_ID}/{ENV_APP_KEY} 环境变量提供。",
            file=sys.stderr,
        )
        sys.exit(2)
    return ClientConfig(
        app_id=app_id,
        app_key=app_key,
        base_url=args.base_url or os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL),
        timeout=float(args.timeout or os.environ.get(ENV_TIMEOUT, DEFAULT_TIMEOUT)),
        verbose=args.verbose or _env_bool(ENV_VERBOSE),
    )


def build_signing_string(method: str, uri: str, date: str, body: bytes) -> str:
    """构造 GuanHai-1 待签名串（与服务端 build_signing_string 同源）。

    body 为原始请求体 bytes；SHA256 对 bytes 直接摘要，
    与服务端 sha256_hex(body.decode('utf-8')) 的摘要结果等价。
    """
    body_hash = hashlib.sha256(body).hexdigest() if body else ""
    return "".join([ALGORITHM, method.upper(), uri, SIGN_CONTENT_TYPE, date, body_hash])


def sign_request(cfg: ClientConfig, method: str, uri: str, body: bytes) -> dict[str, str]:
    """对单次请求生成鉴权请求头。"""
    date = formatdate(timeval=None, localtime=False, usegmt=True)  # RFC1123 GMT
    signing_string = build_signing_string(method=method, uri=uri, date=date, body=body)
    signature = hmac.new(
        cfg.app_key.encode("utf-8"),
        signing_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "X-App-Id": cfg.app_id,
        "X-App-Date": date,
        "X-App-Authorization": f"{ALGORITHM} {cfg.app_id}:{signature}",
    }
    if cfg.verbose:
        print(f"[verbose] 签名串: {signing_string}", file=sys.stderr)
        print(f"[verbose] 签名值: {signature}", file=sys.stderr)
    return headers


def request(
    cfg: ClientConfig, method: str, path: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """发起签名请求（path 需以 / 开头，如 /rag/query）。

    URI 归一约定（GuanHai-1 协议）：参与签名的 URI 为「base_url 路径前缀 +
    path」且统一去除尾部斜杠（/rag/query 与 /rag/query/ 视为同一资源），
    与服务端剥离逻辑（utils.build_auth_context_from_request）同源，
    否则签名必然不匹配。
    """
    if path.startswith("?"):
        norm_path = path
    else:
        base, _, query = path.partition("?")
        norm_path = (base.rstrip("/") or "/") + (f"?{query}" if query else "")
    # 参与签名的 URI 必须包含 base_url 的路径前缀（如 /api/v1），与服务端完整路径一致
    api_prefix = urlparse(cfg.base_url).path.rstrip("/")
    uri = f"{api_prefix}{norm_path}"
    payload = b""
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = sign_request(cfg, method, uri, payload)
    headers["Content-Type"] = "application/json"
    url = f"{cfg.base_url}{path}"
    resp = requests.request(method, url, headers=headers, data=payload, timeout=cfg.timeout)
    try:
        return {"status": resp.status_code, "json": resp.json()}
    except ValueError:
        return {"status": resp.status_code, "text": resp.text}


def main() -> int:
    parser = argparse.ArgumentParser(description="x-GuanHai 开放 API GuanHai-1 签名调用示例")
    parser.add_argument("--app-id", default=os.environ.get(ENV_APP_ID, ""), help="AppId")
    parser.add_argument("--app-key", default=os.environ.get(ENV_APP_KEY, ""), help="AppKey")
    parser.add_argument(
        "--base-url", default=os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL), help="服务地址"
    )
    parser.add_argument(
        "--timeout",
        default=float(os.environ.get(ENV_TIMEOUT, DEFAULT_TIMEOUT)),
        help="请求超时（秒）",
    )
    parser.add_argument("--verbose", action="store_true", help="打印签名串与签名值")
    parser.add_argument(
        "--with-post", action="store_true", help="演示 POST 全链路（需 document:write scope）"
    )
    args = parser.parse_args()

    cfg = load_config(args)
    print(f"Base URL: {cfg.base_url}")

    # GET 演示：RAG 统计（需 rag:read scope）
    print("\n── GET /rag/stats ──")
    result = request(cfg, "GET", "/rag/stats")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # POST 演示：RAG 查询（需 rag:read scope）
    print("\n── POST /rag/query ──")
    result = request(cfg, "POST", "/rag/query", {"query": "观海是什么？", "top_k": 3})
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.with_post:
        print("\n── POST /documents/upload 需 multipart，签名体为 JSON，演示跳过 ──")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
