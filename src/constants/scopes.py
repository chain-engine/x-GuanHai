#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放 API scope 统一目录（scope 元数据的唯一事实来源）。

Scope 的编码 / 中文名 / 所属模块 / 操作类型 / 描述 / 排序号全部在
OpenApiScopeCode 中定义一次；模块与动作词表集中在 OpenApiScopeModule /
OpenApiScopeAction。以下消费方均从本目录派生，禁止再硬编码 scope 码：
    - 开放 API 路由：@app_scope(OpenApiScopeCode.XXX) 挂载元数据，
      require_app_scope(OpenApiScopeCode.XXX.mark) 做鉴权；
    - 启动时路由扫描收集（http_server.scope_decorator.collect_scopes_from_app），
      对账同步由同模块 sync_scopes_to_db 自持会话直接完成；
    - 开放 API 应用管理（创建 App 时校验 scope 合法性）。

动作词表保留 read / write 粗粒度（第三方集成惯例）。
"""

from __future__ import annotations

from typing import cast

from src.constants.base import BaseEnum, StrBaseEnum


class OpenApiScopeModule(StrBaseEnum):
    """开放 API scope 模块编码与中文名映射（与 OpenApiScopeCode.module 一一对应）。"""

    RAG = ("rag", "知识库查询")
    DOCUMENT = ("document", "文档管理")
    ADMIN = ("admin", "开放 API 管理")


class OpenApiScopeAction(StrBaseEnum):
    """开放 API scope 动作词表（scope 码冒号后缀的统一来源）。

    保留 read / write 粗粒度：面向第三方集成方，授权勾选简单。
    """

    READ = ("read", "读取")
    WRITE = ("write", "写入")
    ADMIN = ("admin", "管理")


class OpenApiScopeCode(BaseEnum):
    """开放 API scope 编码及元数据。

    成员值为 6 元组：
        (scope_code, scope_name, module, operation, description, sort_order)
    其中 mark（继承自 BaseEnum）即 scope_code，可直接与裸字符串比较
    （OpenApiScopeCode.RAG_READ == "rag:read"）。
    """

    def __init__(
        self,
        mark: str,
        scope_name: str,
        module: str,
        operation: str,
        description: str,
        sort_order: int,
    ) -> None:
        super().__init__(mark, scope_name)
        self._scope_name = scope_name
        self._module = module
        self._operation = operation
        self._description = description
        self._sort_order = sort_order

    @property
    def scope_name(self) -> str:
        """scope 中文名。"""
        return self._scope_name

    @property
    def module(self) -> str:
        """所属模块编码。"""
        return self._module

    @property
    def operation(self) -> str:
        """操作类型。"""
        return self._operation

    @property
    def description(self) -> str:
        """scope 描述。"""
        return self._description

    @property
    def sort_order(self) -> int:
        """展示排序号。"""
        return self._sort_order

    @property
    def mark(self) -> str:
        """scope 码（覆写收窄为 str，避免与 BaseEnum 的 int|str 联合类型混淆）。"""
        return cast(str, self._mark)

    @property
    def value(self) -> str:
        """scope 码（枚举序列化兼容）。"""
        return cast(str, self._mark)

    # ── 知识库域 ──────────────────────────────────────────
    RAG_READ = (
        "rag:read",
        "知识库查询",
        OpenApiScopeModule.RAG.mark,
        OpenApiScopeAction.READ.mark,
        "调用 RAG 检索与问答接口（query / retrieve / embed / stats）",
        1,
    )
    # ── 文档域 ────────────────────────────────────────────
    DOCUMENT_READ = (
        "document:read",
        "文档读取",
        OpenApiScopeModule.DOCUMENT.mark,
        OpenApiScopeAction.READ.mark,
        "查看文档列表、详情与处理状态",
        2,
    )
    DOCUMENT_WRITE = (
        "document:write",
        "文档写入",
        OpenApiScopeModule.DOCUMENT.mark,
        OpenApiScopeAction.WRITE.mark,
        "上传与删除文档（含重新索引）",
        3,
    )
    # ── 管理域 ────────────────────────────────────────────
    ADMIN = (
        "admin",
        "开放 API 管理",
        OpenApiScopeModule.ADMIN.mark,
        OpenApiScopeAction.ADMIN.mark,
        "开放 API 应用管理（创建 / 吊销 / 启停）",
        4,
    )


__all__ = [
    "OpenApiScopeModule",
    "OpenApiScopeAction",
    "OpenApiScopeCode",
]
