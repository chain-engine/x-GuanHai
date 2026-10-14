#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Infras Package

基础设施层，封装第三方中间件、客户端、连接生命周期。
模块文件平铺：storage.py（文档存储）、embedding.py（嵌入模型）、
vector.py（向量存储抽象基类 + Chroma 实现）、bm25.py（BM25 稀疏索引）、
llm.py（LLM 提供者抽象基类 + 多提供商实现）、
chunking.py（文本切分抽象基类 + LangChain / LlamaIndex 实现）。
"""

from src.infras.storage import DocumentStoreBase, JSONDocumentStore
from src.infras.embedding import EmbeddingModelBase, BGEEmbeddingModel
from src.infras.vector import VectorStoreBase, ChromaVectorStore
from src.infras.bm25 import BM25IndexStore
from src.infras.chunking import (
    BaseChunkingProvider,
    LangchainProvider,
    LlamaIndexProvider,
    TextChunk,
    get_chunking_provider,
    list_chunking_providers,
)
from src.infras.llm import (
    BaseLLMProvider,
    DeepSeekProvider,
    DoubaoProvider,
    AliyunProvider,
    MimoProvider,
    MockProvider,
    get_llm_provider,
    create_chat_model,
    list_providers,
)

__all__ = [
    "DocumentStoreBase",
    "JSONDocumentStore",
    "EmbeddingModelBase",
    "BGEEmbeddingModel",
    "VectorStoreBase",
    "ChromaVectorStore",
    "BM25IndexStore",
    "TextChunk",
    "BaseChunkingProvider",
    "LangchainProvider",
    "LlamaIndexProvider",
    "get_chunking_provider",
    "list_chunking_providers",
    "BaseLLMProvider",
    "DeepSeekProvider",
    "DoubaoProvider",
    "AliyunProvider",
    "MimoProvider",
    "MockProvider",
    "get_llm_provider",
    "create_chat_model",
    "list_providers",
]
