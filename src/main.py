#!/usr/bin/env python3
"""
观海（GuanHai）应用入口

一个支持 HTTP 与 MCP 双挂载的 RAG（检索增强生成）一体化工程框架：
统一开放 API 鉴权（AppId + GuanHai-1 签名），对外提供文档管理与检索问答能力。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from src.constants import HttpStatus
from src.core.config import settings
from src.core.exceptions import AppException
from src.core.logger import logger, setup_logging
from src.core.middleware import setup_middleware
from src.core.seed import init_seed_data
from src.http_server.response import error_response, success_response
from src.http_server.router import api_router
from src.http_server.scope_decorator import sync_scopes_to_db
from src.infras.database import init_database
from src.mcp_server.server import bind_rag_service, mcp_server
from src.rag import Augmentation, LLMGeneration, RAGPipeline, Retrieval
from src.repositories.bm25_repository import BM25Repository
from src.repositories.document_repository import DocumentRepository
from src.repositories.vector_repository import VectorRepository
from src.services.audit_service import AuditService
from src.services.document_service import DocumentService
from src.services.rag_service import RAGService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化日志配置（全局仅一次；控制台 DEBUG 彩色 / 生产 JSON，文件始终 JSON）
    setup_logging()
    logger.info("Starting x-GuanHai application...")

    # 初始化数据库
    init_database()
    logger.info("Database initialized successfully")
    # 自动扫描开放平台路由的 scope 声明，同步到 openapi_scopes 表
    # scope 元数据（含描述 / 排序号）全部来自 OpenApiScopeCode 统一目录
    active_count, deprecated_count = sync_scopes_to_db(app)
    logger.info(f"OpenAPI scopes synchronized successfully: {active_count} active, {deprecated_count} deprecated")
    # 初始化种子数据
    init_seed_data()
    logger.info("Seed data initialized successfully")

    # 初始化审计服务
    audit_service = AuditService()

    # 初始化文档存储 Repository层
    doc_repo = DocumentRepository(storage_path="./data/documents")

    # 初始化 BM25 Repository层（稀疏索引）
    bm25_repo = BM25Repository(
        persist_directory="./data/bm25",
        index_name="documents",
    )

    # 初始化向量存储 Repository层（稠密索引）
    vector_repo = VectorRepository(
        persist_directory=settings.VECTOR_STORE_PERSIST_DIR,
        collection_name=settings.VECTOR_STORE_COLLECTION_NAME,
        distance_type=settings.VECTOR_STORE_DISTANCE,
    )

    # 初始化文档服务（同时构建稠密和稀疏索引）
    document_service = DocumentService(
        vector_repo=vector_repo,
        doc_repo=doc_repo,
        bm25_repo=bm25_repo,
        chunk_size=settings.TEXT_SPLITTER_CHUNK_SIZE,
        chunk_overlap=settings.TEXT_SPLITTER_CHUNK_OVERLAP,
        chunking_provider=settings.TEXT_SPLITTER_PROVIDER,
        chunking_strategy=settings.TEXT_SPLITTER_STRATEGY,
        audit_service=audit_service,
    )

    # 初始化 RAG 服务
    retrieval = Retrieval(
        vector_repo=vector_repo,
        bm25_repo=bm25_repo,
    )
    augmentation = Augmentation()
    generation = LLMGeneration(
        default_provider=settings.GENERATION_PROVIDER,
        default_model=settings.GENERATION_MODEL,
        default_temperature=settings.GENERATION_TEMPERATURE,
        default_max_tokens=settings.GENERATION_MAX_TOKENS,
        default_timeout=settings.GENERATION_TIMEOUT,
    )
    pipeline = RAGPipeline(
        retrieval=retrieval,
        augmentation=augmentation,
        generation=generation,
    )
    rag_service = RAGService(pipeline=pipeline, audit_service=audit_service)

    # 直接存储到 app.state
    app.state.rag_service = rag_service
    app.state.document_service = document_service
    app.state.audit_service = audit_service

    # 将 RAG 服务注入 MCP server，供 /mcp 工具复用同一实例
    bind_rag_service(rag_service)

    # 初始化服务
    rag_service.initialize()
    document_service.initialize()

    logger.info("All services initialized successfully")

    # 手动驱动 MCP 子应用生命周期（Starlette Mount 不会级联执行子应用 lifespan；
    # MCP 2.x 的 StreamableHTTPSessionManager 必须经 run() 初始化 task group）
    mcp_app = getattr(app.state, "mcp_app", None)
    if mcp_app is not None:
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    else:
        yield


    # 关闭服务
    rag_service = getattr(app.state, "rag_service", None)
    document_service = getattr(app.state, "document_service", None)
    if rag_service:
        rag_service.shutdown()
    if document_service:
        document_service.shutdown()

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 配置中间件
    setup_middleware(app)

    # MCP 出口认证中间件：/mcp 与 HTTP 同源（AppId + GuanHai-1 签名）。
    # 注意 add_middleware 后注册先执行，此处置于通用中间件之后，
    # 只拦 /mcp 前缀的 POST 请求，OPTIONS 预检与未启用鉴权时放行。
    from src.mcp_server.auth import OpenApiAuthMiddleware

    app.add_middleware(OpenApiAuthMiddleware)

    # 注册路由
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 挂载 MCP server（streamable HTTP，默认路径 /mcp）。
    # 注意：MCP 2.x 的 streamable_http_app 内部路由已含 streamable_http_path 前缀，
    # 此处将其置为 "/" 以匹配 Starlette mount 剥离前缀后的子路径 "/"，
    # 否则挂载后请求会 404（/mcp → 子应用 path="/"，Route("/mcp") 不匹配）。
    # 子应用 lifespan（session manager run()）由外层 FastAPI lifespan 手动驱动。
    mcp_app = mcp_server.streamable_http_app(streamable_http_path="/")
    app.state.mcp_app = mcp_app
    app.mount("/mcp", mcp_app)

    # 全局异常处理：所有错误统一走 error_response 封装
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """应用异常处理器"""
        logger.error(f"Application exception: {exc.message}")
        return error_response(
            request=request,
            code=exc.code,
            message=exc.message,
            data=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求验证异常处理器"""
        logger.error(f"Validation error: {exc.errors()}")
        return error_response(
            request=request,
            code=HttpStatus.BAD_REQUEST.value,
            message="Validation failed",
            data=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理器"""
        logger.opt(exception=True).error("Unhandled exception occurred")
        return error_response(
            request=request,
            code=HttpStatus.INTERNAL_ERROR.value,
            message="Internal server error",
            data=str(exc) if settings.DEBUG else None,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP 异常处理器（统一 404/400/403 等错误格式）"""
        return error_response(
            request=request,
            code=exc.status_code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            data=None if isinstance(exc.detail, str) else exc.detail,
        )

    # 路由未匹配（Starlette 默认直接返回 {"detail": "Not Found"}，不经过异常链），
    # 替换 Router 默认 handler 使 404 也走统一 error_response 封装。
    async def _not_found_handler(scope, receive, send) -> None:
        request = Request(scope)
        response = error_response(
            request=request,
            code=HttpStatus.NOT_FOUND.value,
            message="Not Found",
        )
        await response(scope, receive, send)

    app.router.default = _not_found_handler

    # 根路径
    @app.get("/", tags=["根路径"])
    async def root(request: Request):
        """根路径"""
        return success_response(
            data={
                "name": settings.APP_ID,
                "version": settings.APP_VERSION,
                "description": settings.APP_DESCRIPTION,
                "docs": "/docs",
                "redoc": "/redoc",
                "openapi": "/openapi.json",
            },
            request=request,
        )

    return app


app = create_app()


def main():
    """CLI 入口点 (供 uv run x-GuanHai 调用)"""
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
        log_level="debug",
    )


if __name__ == "__main__":
    main()
