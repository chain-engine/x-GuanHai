#!/usr/bin/env python3
"""
Schemas Package

统一存放接口请求入参、响应返回Pydantic模型
"""

from src.schemas.base import (
    BaseRequest,
    BaseResponse,
    BaseSchema,
)
from src.schemas.document import (
    DocumentDeleteRequest,
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentQueryRequest,
    DocumentQueryResponse,
    DocumentStatusResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
)
from src.schemas.health import (
    HealthCheckRequest,
    HealthCheckResponse,
    StatusResponse,
    VersionResponse,
)
from src.schemas.rag import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerationRequest,
    GenerationResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedDocument,
)
from src.schemas.responses import (
    ErrorResponse,
    PageModel,
    ResponseModel,
    error_response,
    success_response,
)

__all__ = [
    # Base
    "BaseSchema",
    "BaseRequest",
    "BaseResponse",
    # Responses
    "ResponseModel",
    "PageModel",
    "ErrorResponse",
    "success_response",
    "error_response",
    # RAG
    "RAGQueryRequest",
    "RetrievalRequest",
    "EmbeddingRequest",
    "GenerationRequest",
    "RetrievedDocument",
    "RAGQueryResponse",
    "EmbeddingResponse",
    "RetrievalResponse",
    "GenerationResponse",
    # Document
    "DocumentUploadRequest",
    "DocumentDeleteRequest",
    "DocumentQueryRequest",
    "DocumentInfo",
    "DocumentUploadResponse",
    "DocumentDeleteResponse",
    "DocumentQueryResponse",
    "DocumentStatusResponse",
    # Health
    "HealthCheckRequest",
    "HealthCheckResponse",
    "VersionResponse",
    "StatusResponse",
]
