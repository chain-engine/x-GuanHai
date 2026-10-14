#!/usr/bin/env python3
"""
Router Module

路由注册
"""

from fastapi import APIRouter

from src.http_server.v1 import audit_log, document, health, openapi_app, rag

api_router = APIRouter()

# 注册健康检查路由
api_router.include_router(health.router, tags=["系统"])

# 注册RAG路由
api_router.include_router(rag.router, tags=["RAG"])

# 注册文档管理路由
api_router.include_router(document.router, tags=["文档"])

# 注册审计日志路由（内部管理面，签名 + admin scope 保护）
api_router.include_router(audit_log.router, tags=["审计"])

# 注册开放 API 应用管理路由（内部管理面，签名 + admin scope 保护）
api_router.include_router(openapi_app.router, tags=["开放API应用管理"])
