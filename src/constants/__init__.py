#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Constants Package

统一管理项目中的常量，避免魔法数值和硬编码字符串
"""

from .base import BaseEnum

from .common import (
    # HTTP Status Enum
    HttpStatus,
    # Response Messages Enum
    ResponseMsg,
    # Date/Time Formats
    DATE_FORMAT,
    DATETIME_FORMAT,
    ISO_DATETIME_FORMAT,
    # Pagination
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    # Timeouts
    SHORT_TIMEOUT,
    MEDIUM_TIMEOUT,
    LONG_TIMEOUT,
    # Regex
    EMAIL_REGEX,
    PHONE_REGEX,
    # Headers Enum
    HeaderType,
)

from .env import (
    Environment,
)

from .rag import (
    # Document Status Enum
    DocStatus,
    # Document Types Enum
    DocType,
    SUPPORTED_DOC_TYPES,
    # Distance Types
    DISTANCE_COSINE,
    DISTANCE_EUCLIDEAN,
    DISTANCE_DOT,
    # Default Values
    DEFAULT_TOP_K,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_MMR_LAMBDA,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    # Prompt Templates
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
    # Enums
    DistanceType,
    RerankingProviderName,
)

from .embedding import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_DEVICE,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_CACHE_SIZE,
)

from .vector_store import (
    VectorStoreType,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_DISTANCE,
)

from .generation import (
    LLMProviderType,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT,
    SUPPORTED_LLM_PROVIDERS,
)

from .rate_limit import (
    DEFAULT_REQUESTS_PER_MINUTE,
    DEFAULT_REQUESTS_PER_HOUR,
)

from .log import (
    LogLevel,
)

from .server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    API_PREFIX,
    API_TITLE,
    API_VERSION,
)

from .understanding import (
    IntentType,
    EntityType,
    INTENT_PATTERNS,
    ENTITY_PATTERNS,
    DEFAULT_INTENT_MIN_CONFIDENCE,
    DEFAULT_QUERY_STOPWORDS,
)

__all__ = [
    # BaseEnum
    "BaseEnum",
    # HTTP Status
    "HttpStatus",
    # Response Messages
    "ResponseMsg",
    # Date/Time Formats
    "DATE_FORMAT",
    "DATETIME_FORMAT",
    "ISO_DATETIME_FORMAT",
    # Pagination
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    # Timeouts
    "SHORT_TIMEOUT",
    "MEDIUM_TIMEOUT",
    "LONG_TIMEOUT",
    # Regex
    "EMAIL_REGEX",
    "PHONE_REGEX",
    # Headers
    "HeaderType",
    # Environment
    "Environment",
    # Document Status
    "DocStatus",
    # Document Types
    "DocType",
    "SUPPORTED_DOC_TYPES",
    # Distance Types
    "DISTANCE_COSINE",
    "DISTANCE_EUCLIDEAN",
    "DISTANCE_DOT",
    # RAG Defaults
    "DEFAULT_TOP_K",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_MMR_LAMBDA",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    # Prompt Templates
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_USER_PROMPT_TEMPLATE",
    # RAG Enums
    "DistanceType",
    "RerankingProviderName",
    # LLM Providers
    "LLMProviderType",
    "SUPPORTED_LLM_PROVIDERS",
    # Embedding
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_DEVICE",
    "DEFAULT_EMBEDDING_BATCH_SIZE",
    "DEFAULT_EMBEDDING_CACHE_SIZE",
    # Vector Store
    "VectorStoreType",
    "DEFAULT_COLLECTION_NAME",
    "DEFAULT_DISTANCE",
    # Generation
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT",
    # Rate Limit
    "DEFAULT_REQUESTS_PER_MINUTE",
    "DEFAULT_REQUESTS_PER_HOUR",
    # Log Levels
    "LogLevel",
    # Server
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "API_PREFIX",
    "API_TITLE",
    "API_VERSION",
    # Understanding
    "IntentType",
    "EntityType",
    "INTENT_PATTERNS",
    "ENTITY_PATTERNS",
    "DEFAULT_INTENT_MIN_CONFIDENCE",
    "DEFAULT_QUERY_STOPWORDS",
]
