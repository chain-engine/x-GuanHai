#!/usr/bin/env python3
"""开放 API 应用管理接口（内部管理面）。

仅面向内部管理使用（签名鉴权 + admin scope 保护），不建议暴露公网：
- 创建 App：返回明文 AppKey（仅此一次）；
- 列表 / 吊销 / 启用 / 物理删除：应用生命周期管理。

首个 admin 应用由启动种子（core.seed.init_seed_data，固定默认凭据）或
scripts/manage_openapi_app.py 创建；之后管理面用签名调用本组接口。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from src.constants import HttpStatus
from src.constants.scopes import OpenApiScopeCode
from src.http_server.dependencies import (
    get_app_operator_context,
    get_openapi_app_service,
    require_app_scope,
)
from src.http_server.response import success_response
from src.http_server.scope_decorator import app_scope
from src.schemas.openapi_app import (
    OpenApiAppCreateRequest,
    OpenApiAppCreateResponse,
    OpenApiAppItem,
    OpenApiCurrentApp,
)
from src.schemas.responses import ResponseModel
from src.services.openapi_app_service import OpenApiAppService

router = APIRouter(prefix="/apps", tags=["开放API应用管理"])


@router.get(
    "",
    summary="开放 API 应用列表",
    response_model=ResponseModel,
)
@app_scope(OpenApiScopeCode.ADMIN)
def list_apps(
    request: Request,
    keyword: str | None = Query(default=None, description="按名称关键字过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页记录数"),
    service: OpenApiAppService = Depends(get_openapi_app_service),
    current_app: OpenApiCurrentApp = Depends(require_app_scope(OpenApiScopeCode.ADMIN.mark)),
) -> dict[str, Any]:
    """应用列表（不返回任何密钥信息）。"""
    operator = get_app_operator_context(current_app, request)
    result = service.list_apps(keyword=keyword, page=page, page_size=page_size, operator=operator)
    return success_response(data=result.model_dump(), request=request)


@router.post(
    "",
    summary="创建开放 API 应用",
    response_model=ResponseModel,
    status_code=201,
)
@app_scope(OpenApiScopeCode.ADMIN)
def create_app(
    request: Request,
    body: OpenApiAppCreateRequest,
    service: OpenApiAppService = Depends(get_openapi_app_service),
    current_app: OpenApiCurrentApp = Depends(require_app_scope(OpenApiScopeCode.ADMIN.mark)),
) -> dict[str, Any]:
    """创建应用，返回明文 AppKey（仅此一次，请立即保存）。"""
    operator = get_app_operator_context(current_app, request)
    result: OpenApiAppCreateResponse = service.create_app(body, operator=operator)
    return success_response(
        data=result.model_dump(),
        request=request,
        code=HttpStatus.CREATED.value,
        message="AppKey 明文仅返回一次，请立即保存",
    )


@router.delete(
    "/{app_id}",
    summary="吊销开放 API 应用",
    response_model=ResponseModel,
)
@app_scope(OpenApiScopeCode.ADMIN)
def revoke_app(
    request: Request,
    app_id: str,
    service: OpenApiAppService = Depends(get_openapi_app_service),
    current_app: OpenApiCurrentApp = Depends(require_app_scope(OpenApiScopeCode.ADMIN.mark)),
) -> dict[str, Any]:
    """吊销应用（status → disabled，即时生效，不影响历史调用记录）。"""
    operator = get_app_operator_context(current_app, request)
    item: OpenApiAppItem = service.revoke_app(app_id, operator=operator)
    return success_response(data=item.model_dump(), request=request, message="应用已吊销")


@router.post(
    "/{app_id}/enable",
    summary="重新启用开放 API 应用",
    response_model=ResponseModel,
)
@app_scope(OpenApiScopeCode.ADMIN)
def enable_app(
    request: Request,
    app_id: str,
    service: OpenApiAppService = Depends(get_openapi_app_service),
    current_app: OpenApiCurrentApp = Depends(require_app_scope(OpenApiScopeCode.ADMIN.mark)),
) -> dict[str, Any]:
    """重新启用应用（status → active）。"""
    operator = get_app_operator_context(current_app, request)
    item: OpenApiAppItem = service.enable_app(app_id, operator=operator)
    return success_response(data=item.model_dump(), request=request, message="应用已启用")


@router.delete(
    "/{app_id}/purge",
    summary="物理删除开放 API 应用",
    response_model=ResponseModel,
)
@app_scope(OpenApiScopeCode.ADMIN)
def purge_app(
    request: Request,
    app_id: str,
    service: OpenApiAppService = Depends(get_openapi_app_service),
    current_app: OpenApiCurrentApp = Depends(require_app_scope(OpenApiScopeCode.ADMIN.mark)),
) -> dict[str, Any]:
    """物理删除应用记录（清理用途；常规吊销请用 DELETE /apps/{app_id}）。"""
    operator = get_app_operator_context(current_app, request)
    service.delete_app(app_id, operator=operator)
    return success_response(data={"app_id": app_id}, request=request, message="应用已删除")


__all__ = ["router"]
