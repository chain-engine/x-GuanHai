#!/usr/bin/env python3
"""生成带 GuanHai-1 签名头的 curl 命令（免手算 HMAC 签名）。

用法示例：
    python scripts/sign_curl.py --body '{"query":"什么是RAG技术？","top_k":3}'
    python scripts/sign_curl.py --url http://127.0.0.1:8000/api/v1/rag/stats --method GET
    python scripts/sign_curl.py --app-id app --app-key gk_admin_change_me --body '<json>'

输出可直接粘贴执行的 curl 命令（含 X-App-Id / X-App-Date / X-App-Authorization）。
签名头有时效（默认 300 秒），过期需重新生成。
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import sys
from email.utils import formatdate
from urllib.parse import urlparse

ALGORITHM = "GuanHai-1"
CONTENT_TYPE = "application/json"


def build_signing_string(method: str, uri: str, date: str, body: bytes) -> str:
    """签名串 = Ver + METHOD + URI + Content-Type + Date + SHA256(body)（与 src/core/signature.py 同源）。"""
    body_hash = hashlib.sha256(body).hexdigest() if body else ""
    return "".join([ALGORITHM, method.upper(), uri, CONTENT_TYPE, date, body_hash])


def main() -> int:
    parser = argparse.ArgumentParser(description="生成带 GuanHai-1 签名头的 curl 命令")
    parser.add_argument("--app-id", default="app", help="开放应用 AppId（默认种子应用 app）")
    parser.add_argument("--app-key", default="gk_admin_change_me", help="AppKey（默认种子密钥）")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/rag/query", help="完整请求 URL")
    parser.add_argument("--method", default="POST", help="HTTP 方法（GET/POST/PUT/DELETE）")
    parser.add_argument("--body", default=None, help='请求体 JSON 字符串；GET 可省略（如 --body "{}"）')
    parser.add_argument("--verbose", action="store_true", help="额外打印签名串与签名值")
    args = parser.parse_args()

    parsed = urlparse(args.url)
    # URI 归一（GuanHai-1 协议）：path 去除尾部斜杠，保留查询串
    uri = (parsed.path.rstrip("/") or "/") + (f"?{parsed.query}" if parsed.query else "")
    body = args.body.encode("utf-8") if args.body is not None else b""
    date = formatdate(timeval=None, localtime=False, usegmt=True)  # RFC1123 GMT
    signing_string = build_signing_string(args.method, uri, date, body)
    sig = hmac.new(args.app_key.encode("utf-8"), signing_string.encode("utf-8"), hashlib.sha256).hexdigest()

    headers = [
        f"-H 'X-App-Id: {args.app_id}'",
        f"-H 'X-App-Date: {date}'",
        f"-H 'X-App-Authorization: {ALGORITHM} {args.app_id}:{sig}'",
        "-H 'Content-Type: application/json'",
    ]
    body_arg = f" -d '{args.body}'" if args.body is not None else ""
    print(f"curl -X '{args.method}' '{args.url}' {' '.join(headers)}{body_arg}")

    if args.verbose:
        print(f"\n# 签名串: {signing_string}", file=sys.stderr)
        print(f"# 签名值: {sig}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
