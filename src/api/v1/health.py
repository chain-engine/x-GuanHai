#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Health Check API Module

健康检查和系统状态接口
"""

from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, Request

from schemas.responses import ResponseModel
from core.logger import logger
from core.config import settings
from services.rag_service import RAGService
from services.document_service import DocumentService

router = APIRouter()

_start_time = datetime.utcnow()


def get_rag_service(request: Request) -> RAGService:
    """依赖注入：获取RAG服务"""
    return request.app.state.rag_service


def get_document_service(request: Request) -> DocumentService:
    """依赖注入：获取文档服务"""
    return request.app.state.document_service


@router.get(
    "/health",
    summary="健康检查",
    description="检查系统健康状态",
    tags=["系统"],
    response_model=ResponseModel,
)
async def health_check(
    rag_service: RAGService = Depends(get_rag_service),
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """健康检查接口"""
    checks = {}

    # 检查向量存储
    try:
        vector_count = rag_service.get_vector_count()
        checks["vector_store"] = "healthy"
        checks["vector_count"] = vector_count
    except Exception as e:
        checks["vector_store"] = f"unhealthy: {str(e)}"

    # 检查文档存储
    try:
        doc_stats = document_service.get_stats()
        checks["document_store"] = "healthy"
        checks["document_count"] = doc_stats.get("document_stats", {}).get("document_count", 0)
    except Exception as e:
        checks["document_store"] = f"unhealthy: {str(e)}"

    data = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }
    return ResponseModel(data=data).model_dump()


@router.get(
    "/version",
    summary="版本信息",
    description="获取系统版本信息",
    tags=["系统"],
    response_model=ResponseModel,
)
async def get_version() -> dict[str, Any]:
    """版本信息接口"""
    data = {
        "version": settings.APP_VERSION,
        "name": settings.APP_ID,
        "description": settings.APP_DESCRIPTION,
    }
    return ResponseModel(data=data).model_dump()


@router.get(
    "/status",
    summary="系统状态",
    description="获取系统运行状态",
    tags=["系统"],
    response_model=ResponseModel,
)
async def get_status(
    rag_service: RAGService = Depends(get_rag_service),
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """系统状态接口"""
    uptime = (datetime.utcnow() - _start_time).total_seconds()
    vector_count = 0
    document_count = 0

    try:
        vector_count = rag_service.get_vector_count()
    except Exception as e:
        logger.warning(f"Failed to get vector count: {e}")

    try:
        doc_stats = document_service.get_stats()
        document_count = doc_stats.get("document_stats", {}).get("document_count", 0)
    except Exception as e:
        logger.warning(f"Failed to get document count: {e}")

    data = {
        "status": "running",
        "uptime": uptime,
        "memory_usage": {},
        "vector_count": vector_count,
        "document_count": document_count,
    }
    return ResponseModel(data=data).model_dump()
