#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main Entry Point

FastAPI应用入口
"""

import sys
from pathlib import Path

# 添加src目录到路径
src_dir = Path(__file__).parent.resolve()
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.logger import logger
from core.config import settings
from core.middleware import setup_middleware
from core.exceptions import AppException
from repositories.vector_repository import VectorRepository
from repositories.document_repository import DocumentRepository
from repositories.bm25_repository import BM25Repository
from rag import Retrieval, Augmentation, LLMGeneration, RAGPipeline
from services.rag_service import RAGService
from services.document_service import DocumentService
from api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting x-GuanHai application...")

    try:        
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
        rag_service = RAGService(pipeline=pipeline)

        # 直接存储到 app.state
        app.state.rag_service = rag_service
        app.state.document_service = document_service

        # 初始化服务
        rag_service.initialize()
        document_service.initialize()

        logger.info("All services initialized successfully")

        yield

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        logger.info("Shutting down x-GuanHai application...")

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

    # 注册路由
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 全局异常处理
    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc: AppException):
        """应用异常处理器"""
        logger.error(f"Application exception: {exc.message}")
        return JSONResponse(
            status_code=exc.code,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        """请求验证异常处理器"""
        logger.error(f"Validation error: {exc.errors()}")
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "message": "Validation failed",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc: Exception):
        """通用异常处理器"""
        logger.opt(exception=True).error("Unhandled exception occurred")
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "Internal server error",
                "detail": str(exc) if settings.DEBUG else None,
            },
        )

    # 根路径
    @app.get("/", tags=["根路径"])
    async def root():
        """根路径"""
        return {
            "name": "x-GuanHai",
            "version": settings.API_VERSION,
            "description": "A production-ready RAG integrated engineering framework",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }

    return app


app = create_app()


def run():
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
    run()