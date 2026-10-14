#!/usr/bin/env python3
"""MCP 工具原语（Tools）——当前暴露只读检索技能。

注册方式：由 server._register_all 调用 register_tools(server, get_rag_service)，
工具实现经闭包捕获服务获取函数，避免本模块与装配层（server.py）循环依赖。

新增工具约定：在本文件 register_tools 内追加 @server.tool() 函数，
保持"只读 + 复用 services"原则（文档上传 / 删除等写操作继续走 HTTP 管理面）。

操作人透传：工具函数声明 ctx: Context 参数（MCP 2.x 自动注入），
经 _resolve_operator 解析当前请求的操作人上下文后，作为 operator 传入
rag_service.retrieve / query（services 层审计落库）：
    - 主通道：认证中间件设置的 contextvar（与下游 app 同 task，可见性已验证）；
    - 兜底：ctx.transport.headers 中的 X-App-Id 反查认证缓存。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context

from src.constants import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K,
)
from src.core.exceptions import GenerationError, RetrievalError
from src.core.logger import logger
from src.mcp_server.auth import get_current_operator, resolve_operator
from src.schemas.rag import RetrievedDocument
from src.services.rag_service import RAGService

# MCP 请求头中的 AppId 头名（与 HTTP 开放接口头一致，见 constants）
_X_APP_ID_HEADER = "X-App-Id"


def _resolve_operator(ctx: Context) -> dict[str, Any] | None:
    """解析当前 MCP 请求的操作人上下文（审计用）。

    优先级：
        1. contextvar 主通道：认证中间件在同 task 内设置，工具执行时读取；
        2. headers 反查兜底：从 ctx.transport.headers 提取 X-App-Id，
           在认证缓存中反查（防御 context 不传播的调度路径）。
    均未命中返回 None（系统操作，不记录 operator）。
    """
    operator = get_current_operator()
    if operator is not None:
        return operator

    app_id = None
    transport = getattr(ctx, "transport", None)
    if transport is not None:
        for key, value in (transport.headers or {}).items():
            if key.lower() == _X_APP_ID_HEADER.lower():
                app_id = value
                break
    return resolve_operator(app_id)


def _to_mcp_error(exc: Exception) -> Exception:
    """将底层异常转换为 MCP 客户端可读的错误并记录日志，避免泄漏内部堆栈"""
    if isinstance(exc, (RetrievalError, GenerationError)):
        logger.error(f"MCP tool error: {exc.message}")
        return ValueError(exc.message)
    logger.opt(exception=True).error("MCP tool unhandled error")
    return RuntimeError(f"Internal error: {exc}")


def register_tools(
    server: MCPServer,
    get_rag_service: Callable[[], RAGService],
) -> None:
    """注册 MCP 工具（只读 RAG 能力）。"""

    @server.tool()
    def retrieve_docs(
        query: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        use_mmr: bool = False,
        mmr_lambda: float = DEFAULT_MMR_LAMBDA,
        metadata_filter: dict[str, object] | None = None,
        ctx: Context | None = None,
    ) -> list[dict[str, object]]:
        """检索与查询最相关的知识片段，返回片段文本、相似度分数与元数据（仅检索，不生成）。

        Args:
            query: 用户查询内容，支持中英文。
            top_k: 返回的相关文档数量。
            similarity_threshold: 相似度阈值，低于该值的文档被过滤。
            use_mmr: 是否使用 MMR 算法增加结果多样性。
            mmr_lambda: MMR 参数，0.0=多样性优先，1.0=相关性优先。
            metadata_filter: 元数据过滤条件，如 {"file_type": "pdf"}。

        Returns:
            检索到的文档列表，每项含 chunk_id/document_id/text/score/metadata。
        """
        try:
            documents = get_rag_service().retrieve(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                use_mmr=use_mmr,
                mmr_lambda=mmr_lambda,
                metadata_filter=metadata_filter,
                operator=_resolve_operator(ctx) if ctx is not None else None,
            )
            return [doc.model_dump() for doc in RetrievedDocument.from_search_results(documents)]
        except Exception as exc:  # noqa: BLE001 - 统一转换为 MCP 可读错误
            raise _to_mcp_error(exc) from exc

    @server.tool()
    async def rag_query(
        query: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        use_mmr: bool = False,
        mmr_lambda: float = DEFAULT_MMR_LAMBDA,
        metadata_filter: dict[str, object] | None = None,
        provider: str | None = None,
        temperature: float | None = DEFAULT_TEMPERATURE,
        max_tokens: int | None = DEFAULT_MAX_TOKENS,
        ctx: Context | None = None,
    ) -> dict[str, object]:
        """基于知识库内容生成完整回答（检索→增强→生成），返回答案与引用片段。

        Args:
            query: 用户查询内容，支持中英文。
            top_k: 检索数量。
            similarity_threshold: 相似度阈值，低于该值的文档被过滤。
            use_mmr: 是否使用 MMR 算法增加结果多样性。
            mmr_lambda: MMR 参数，0.0=多样性优先，1.0=相关性优先。
            metadata_filter: 元数据过滤条件，如 {"file_type": "pdf"}。
            provider: LLM 提供商，为空使用默认提供商。
            temperature: 生成温度，0.0=确定性，2.0=创造性。
            max_tokens: 生成回答的最大 token 数。

        Returns:
            完整回答：answer/retrieved_docs/provider/model/tokens_used。
        """
        try:
            result = await get_rag_service().query(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                use_mmr=use_mmr,
                mmr_lambda=mmr_lambda,
                metadata_filter=metadata_filter,
                provider=provider,
                temperature=temperature,
                max_tokens=max_tokens,
                operator=_resolve_operator(ctx) if ctx is not None else None,
            )
            # 对齐 RAGQueryResponse 的字段结构，便于客户端消费
            return {
                "answer": result.get("answer", ""),
                "retrieved_docs": result.get("retrieved_docs", []),
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
                "tokens_used": result.get("tokens_used"),
            }
        except Exception as exc:  # noqa: BLE001 - 统一转换为 MCP 可读错误
            raise _to_mcp_error(exc) from exc


__all__ = ["register_tools"]
