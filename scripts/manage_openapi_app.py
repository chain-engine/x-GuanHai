#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放 API 应用管理 CLI（内部管理面的主要通道）。

用法（在项目根目录执行）：
    python scripts/manage_openapi_app.py create --name "第三方Agent" --scopes rag:read --description "..."
    python scripts/manage_openapi_app.py list [--keyword 关键词] [--page 1] [--page-size 20]
    python scripts/manage_openapi_app.py revoke --app-id gh_xxx
    python scripts/manage_openapi_app.py enable --app-id gh_xxx
    python scripts/manage_openapi_app.py delete --app-id gh_xxx

说明：
- 输出为 JSON，便于脚本消费；
- create 返回的 app_key 为明文（仅此一次，请立即保存）；
- 本 CLI 直连数据库（读取 .env / config.yaml 中的 OPENAPI_DB_URL），
  不经过 HTTP 管理接口，适合完全离线管理的部署形态。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 将项目根加入 sys.path（脚本从项目根或任意目录运行均可用）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _get_app_service():
    """初始化数据库并返回 OpenApiAppService 实例。"""
    from src.infras.database import get_session, init_database
    from src.services.openapi_app_service import build_openapi_app_service

    init_database()
    session = get_session()
    return build_openapi_app_service(session), session


def _cmd_create(args: argparse.Namespace) -> int:
    from src.schemas.openapi_app import OpenApiAppCreateRequest

    service, session = _get_app_service()
    try:
        result = service.create_app(
            OpenApiAppCreateRequest(
                name=args.name,
                description=args.description,
                scopes=args.scopes,
                rate_limit_per_minute=args.rate_limit,
            )
        )
        session.commit()
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        print("\n# 请立即保存 app_key（明文仅此一次）", file=sys.stderr)
        return 0
    finally:
        session.close()


def _cmd_list(args: argparse.Namespace) -> int:
    service, session = _get_app_service()
    try:
        result = service.list_apps(keyword=args.keyword, page=args.page, page_size=args.page_size)
        print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        return 0
    finally:
        session.close()


def _cmd_revoke(args: argparse.Namespace) -> int:
    service, session = _get_app_service()
    try:
        item = service.revoke_app(args.app_id)
        session.commit()
        print(json.dumps(item.model_dump(), ensure_ascii=False, indent=2))
        return 0
    finally:
        session.close()


def _cmd_enable(args: argparse.Namespace) -> int:
    service, session = _get_app_service()
    try:
        item = service.enable_app(args.app_id)
        session.commit()
        print(json.dumps(item.model_dump(), ensure_ascii=False, indent=2))
        return 0
    finally:
        session.close()


def _cmd_delete(args: argparse.Namespace) -> int:
    service, session = _get_app_service()
    try:
        service.delete_app(args.app_id)
        session.commit()
        print(json.dumps({"deleted": args.app_id}, ensure_ascii=False))
        return 0
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="开放 API 应用管理 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="创建应用（返回明文 AppKey，仅一次）")
    p_create.add_argument("--name", required=True, help="应用名")
    p_create.add_argument("--description", default="", help="应用描述")
    p_create.add_argument(
        "--scopes",
        nargs="+",
        required=True,
        help="授权 scope 列表，如 rag:read document:read（合法值见 constants/scopes.py）",
    )
    p_create.add_argument("--rate-limit", type=int, default=60, help="每分钟限流次数")
    p_create.set_defaults(func=_cmd_create)

    p_list = sub.add_parser("list", help="列出应用")
    p_list.add_argument("--keyword", default=None, help="按名称关键字过滤")
    p_list.add_argument("--page", type=int, default=1, help="页码")
    p_list.add_argument("--page-size", type=int, default=20, help="每页记录数")
    p_list.set_defaults(func=_cmd_list)

    p_revoke = sub.add_parser("revoke", help="吊销应用（禁用，即时生效）")
    p_revoke.add_argument("--app-id", required=True, help="应用ID")
    p_revoke.set_defaults(func=_cmd_revoke)

    p_enable = sub.add_parser("enable", help="重新启用应用")
    p_enable.add_argument("--app-id", required=True, help="应用ID")
    p_enable.set_defaults(func=_cmd_enable)

    p_delete = sub.add_parser("delete", help="物理删除应用（清理用途）")
    p_delete.add_argument("--app-id", required=True, help="应用ID")
    p_delete.set_defaults(func=_cmd_delete)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
