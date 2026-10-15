#!/usr/bin/env python3
"""观海（GuanHai）命令行启动入口。

应用入口（FastAPI 组装）见 src/main.py；本模块只负责命令行启动。

用法（项目根执行，等价于 uv run x-GuanHai）：
    uv run x-GuanHai                # 默认启动：监听地址/端口取配置，热重载跟随 DEBUG
    uv run x-GuanHai --reload       # 显式开启热重载（修改代码自动重启）
    uv run x-GuanHai --no-reload    # 显式关闭热重载（生产环境）
    uv run x-GuanHai --port 8000    # 覆盖监听端口
    uv run x-GuanHai --host 0.0.0.0 # 覆盖监听地址
    uv run x-GuanHai --workers 4    # 多进程部署（热重载模式强制为 1）

热重载约定：
    - 默认行为跟随配置：DEBUG=true → 自动开启热重载
    - 显式传 --reload / --no-reload 可覆盖默认行为
"""

from __future__ import annotations

import argparse
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="x-GuanHai",
        description="观海（GuanHai）RAG 服务启动器（FastAPI + Uvicorn，HTTP / MCP 双挂载）",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="监听地址（默认取配置 settings.SERVER_HOST）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="监听端口（默认取配置 settings.SERVER_PORT，当前为 8000）",
    )
    parser.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        default=None,
        help="开启热重载（开发环境默认跟随 DEBUG；显式指定以覆盖默认）",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="关闭热重载",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Worker 进程数（生产多进程部署；热重载模式强制为 1）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """启动观海后端服务。"""
    args = _parse_args(argv)

    import uvicorn

    # 延迟加载配置：确保 .env / config.yaml 已加载后再启动
    from src.core.config import settings
    from src.core.logger import logger

    host = args.host or settings.SERVER_HOST
    port = args.port or settings.SERVER_PORT

    # 热重载：未显式指定时，跟随 DEBUG 配置（开发环境默认 true → 自动热重载）
    reload_enabled = args.reload if args.reload is not None else settings.DEBUG

    workers = args.workers or 1
    if reload_enabled and workers != 1:
        logger.warning("热重载模式不支持多 Worker，已强制为 1")
        workers = 1

    if reload_enabled:
        logger.info("热重载已开启（DEBUG=true）；修改代码后服务自动重启")
    logger.info(f"观海后端启动：http://{host}:{port}  |  接口文档 http://{host}:{port}/docs")

    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        workers=workers,
        log_level="info",
    )


if __name__ == "__main__":
    main(sys.argv[1:])
