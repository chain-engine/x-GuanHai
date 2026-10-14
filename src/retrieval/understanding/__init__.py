# -*- coding: utf-8 -*-
"""
Retrieval/Understanding Package

Stage 1 — 查询理解子包
"""

from src.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)
from src.retrieval.understanding.rewrite import (
    QueryRewriteProvider,
    LLMQueryRewriter,
    SimpleQueryRewriter,
)
from src.retrieval.understanding.expansion import (
    QueryExpansionProvider,
    SynonymExpander,
    EmbeddingExpander,
)
from src.retrieval.understanding.preprocess import (
    QueryPreprocessor,
)
from src.retrieval.understanding.intent import (
    IntentClassifier,
)
from src.retrieval.understanding.entity import (
    EntityExtractor,
)

# IntentType / EntityType 已迁移至 constants.understanding
from src.constants import IntentType, EntityType

__all__ = [
    # Base
    "BaseQueryUnderstandingProvider",
    "QueryUnderstandingResult",
    # Rewrite
    "QueryRewriteProvider",
    "LLMQueryRewriter",
    "SimpleQueryRewriter",
    # Expansion
    "QueryExpansionProvider",
    "SynonymExpander",
    "EmbeddingExpander",
    # Preprocess
    "QueryPreprocessor",
    # Intent
    "IntentClassifier",
    "IntentType",  # re-exported from constants
    # Entity
    "EntityExtractor",
    "EntityType",  # re-exported from constants
]
