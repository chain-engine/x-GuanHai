#!/usr/bin/env python3
"""GuanHai HTTP 客户端：以第三方应用视角接入观海开放 API（自动完成 GuanHai-1 签名）。

适用对象：需要调用观海 HTTP 开放接口的外部程序/Agent（如小爱、小蓝等）。

两种使用方式：

1. 命令行方式（快速验证/调试）：
    python scripts/guanhai_http_client.py --url http://127.0.0.1:8000/api/v1/rag/stats --method GET
    python scripts/guanhai_http_client.py --url http://127.0.0.1:8000/api/v1/rag/query \
        --method POST --body-file body.json

2. 编程方式（集成进自己的代码）：
    from scripts.guanhai_http_client import GuanHaiHTTPClient
    client = GuanHaiHTTPClient("http://127.0.0.1:8000", app_id="app", app_key="gk_admin_change_me")
    data = client.rag_query("什么是RAG技术？", top_k=3)      # -> 响应 JSON 的 data 字段
    stats = client.rag_stats()                                # -> 响应 JSON 的 data 字段

签名协议（与 src/core/signature.py 同源）：
    签名串 = GuanHai-1 + METHOD + URI + application/json + X-App-Date + SHA256(body)
    请求头 = X-App-Id / X-App-Date(RFC1123 GMT) / X-App-Authorization(GuanHai-1 {app_id}:{HMAC})

注意：
    - Windows PowerShell 传参时双引号会被剥离，含引号的 JSON 请用 --body-file；
    - 签名基于实际发送的 body 字节计算，编程方式传入 dict 时由本客户端统一序列化，保证一致。
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from email.utils import formatdate
from typing import Any
from urllib.parse import urlparse

import requests

ALGORITHM = "GuanHai-1"
CONTENT_TYPE = "application/json"


def _build_signing_string(method: str, uri: str, date: str, body: bytes) -> str:
    """签名串 = Ver + METHOD + URI + Content-Type + Date + SHA256(body)。"""
    body_hash = hashlib.sha256(body).hexdigest() if body else ""
    return "".join([ALGORITHM, method.upper(), uri, CONTENT_TYPE, date, body_hash])


class GuanHaiHTTPClient:
    """观海 HTTP 开放 API 客户端。

    构造后即可发起任意开放接口请求，签名头由客户端自动计算并携带；
    verbose=True 时打印完整签名过程与响应，便于排查 401。
    """

    def __init__(
        self,
        base_url: str,
        app_id: str = "app",
        app_key: str = "gk_admin_change_me",
        verbose: bool = True,
        timeout: int = 90,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.app_key = app_key
        self.verbose = verbose
        self.timeout = timeout

    # ── 核心请求方法 ──────────────────────────────────────────────
    def request(self, method: str, path: str, body: Any = None) -> dict[str, Any]:
        """发起一个开放接口请求并返回响应 JSON（dict）。

        Args:
            method: HTTP 方法（GET/POST/PUT/DELETE）。
            path: 接口路径（含前缀），如 /api/v1/rag/query、/api/v1/rag/stats。
            body: 请求体。可为 dict/list（自动 JSON 序列化）、str（按原文发送）或 None。

        Returns:
            服务端响应 JSON（含 code/message/data/request_id）。

        Raises:
            RuntimeError: 请求异常或响应非 2xx。
        """
        url = f"{self.base_url}{path}"
        parsed = urlparse(url)
        # URI 归一（GuanHai-1 协议）：path 去除尾部斜杠，保留 query
        uri = (parsed.path.rstrip("/") or "/") + (f"?{parsed.query}" if parsed.query else "")

        # body 统一为字节：签名与发送使用同一字节序列，避免 401 经典坑
        payload: bytes
        body_display: str | None
        if body is None:
            payload, body_display = b"", None
        elif isinstance(body, (dict, list)):
            body_display = json.dumps(body, ensure_ascii=False)
            payload = body_display.encode("utf-8")
        elif isinstance(body, str):
            body_display = body
            payload = body.encode("utf-8")
        else:
            raise TypeError(f"不支持的 body 类型: {type(body)}")

        date = formatdate(timeval=None, localtime=False, usegmt=True)  # RFC1123 GMT
        signing_string = _build_signing_string(method, uri, date, payload)
        signature = hmac.new(
            self.app_key.encode("utf-8"), signing_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        headers = {
            "X-App-Id": self.app_id,
            "X-App-Date": date,
            "X-App-Authorization": f"{ALGORITHM} {self.app_id}:{signature}",
            "Content-Type": CONTENT_TYPE,
        }

        if self.verbose:
            self._print_signing(method, url, uri, date, body_display, payload, signing_string, signature, headers)

        try:
            resp = requests.request(method, url, headers=headers, data=payload or None, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RuntimeError(f"请求异常：{exc}") from exc

        print(f"响应状态      : {resp.status_code}")
        if self.verbose:
            print("响应头        :", json.dumps(dict(resp.headers.items()), ensure_ascii=False))
        print("响应体        :")
        try:
            result = resp.json()
        except ValueError:
            result = {"raw": resp.text[:2000]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if resp.status_code >= 400:
            raise RuntimeError(f"接口返回 HTTP {resp.status_code}：{json.dumps(result, ensure_ascii=False)[:300]}")
        return result

    # ── 便捷方法（按接口语义封装） ─────────────────────────────────
    def rag_query(self, query: str, top_k: int = 3, **kwargs: Any) -> dict[str, Any]:
        """RAG 问答（检索 → 增强 → 生成）。"""
        body = {"query": query, "top_k": top_k, **kwargs}
        return self.request("POST", "/api/v1/rag/query", body=body)["data"]

    def rag_retrieve(self, query: str, top_k: int = 3, **kwargs: Any) -> dict[str, Any]:
        """仅检索（不经过 LLM 生成）。"""
        body = {"query": query, "top_k": top_k, **kwargs}
        return self.request("POST", "/api/v1/rag/retrieve", body=body)["data"]

    def rag_stats(self) -> dict[str, Any]:
        """向量库统计。"""
        return self.request("GET", "/api/v1/rag/stats")["data"]

    # ── 内部工具 ───────────────────────────────────────────────────
    @staticmethod
    def _print_signing(
        method: str,
        url: str,
        uri: str,
        date: str,
        body_display: str | None,
        payload: bytes,
        signing_string: str,
        signature: str,
        headers: dict[str, str],
    ) -> None:
        print("================= GuanHai-1 HTTP 签名 =================")
        print("[1] 请求方法    :", method)
        print("[2] 完整URL     :", url)
        print("[3] 签名URI     :", uri)
        print("[4] X-App-Date  :", date)
        print("[5] body 原文   :", body_display if body_display is not None else "(空)")
        print("[6] SHA256(body):", hashlib.sha256(payload).hexdigest() if payload else "(空)")
        print("[7] 签名串      :", signing_string)
        print("[8] 签名值      :", signature)
        print("[9] 实际请求头  :")
        for key, value in headers.items():
            print(f"      {key:<22}: {value}")
        print("-------------------------------------------------------")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GuanHai HTTP 客户端（自动完成 GuanHai-1 签名）",
        epilog="示例：\n"
        "  python scripts/guanhai_http_client.py --url http://127.0.0.1:8000/api/v1/rag/stats\n"
        "  python scripts/guanhai_http_client.py --url http://127.0.0.1:8000/api/v1/rag/query "
        "--method POST --body-file body.json",
    )
    parser.add_argument("--url", required=True, help="完整请求 URL，如 http://127.0.0.1:8000/api/v1/rag/query")
    parser.add_argument("--method", default="GET", help="HTTP 方法（GET/POST/PUT/DELETE），默认 GET")
    parser.add_argument("--body", default=None, help='请求体 JSON 字符串（POST/PUT 时传入，如 \'{"query":"xxx"}\'）')
    parser.add_argument(
        "--body-file",
        default=None,
        help="从文件读取请求体 JSON（UTF-8）。Windows PowerShell 传参时双引号会被剥离，"
        "含引号的 JSON 建议用 --body-file",
    )
    parser.add_argument("--app-id", default="app", help="开放应用 AppId（默认种子应用 app）")
    parser.add_argument("--app-key", default="gk_admin_change_me", help="AppKey（默认种子密钥）")
    parser.add_argument("--quiet", action="store_true", help="关闭签名过程日志（仅打印响应）")
    parser.add_argument("--timeout", type=int, default=90, help="请求超时秒数（默认 90，embedding 冷启动可调大）")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        body: Any
        if args.body_file:
            with open(args.body_file, encoding="utf-8") as fh:
                body = fh.read()
        elif args.body is not None:
            body = args.body
        else:
            body = None
        client = GuanHaiHTTPClient(
            base_url=args.url,
            app_id=args.app_id,
            app_key=args.app_key,
            verbose=not args.quiet,
            timeout=args.timeout,
        )
        client.request(args.method, "", body=body)
        return 0
    except (RuntimeError, TypeError, OSError) as exc:
        print(f"✗ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
