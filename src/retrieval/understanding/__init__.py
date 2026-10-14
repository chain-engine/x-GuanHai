"""
Retrieval/Understanding Package

Stage 1 — 查询理解子包
"""

# IntentType / EntityType 已迁移至 constants.understanding
from src.constants import EntityType, IntentType
from src.retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult,
)
from src.retrieval.understanding.entity import (
    EntityExtractor,
)
from src.retrieval.understanding.expansion import (
    EmbeddingExpander,
    QueryExpansionProvider,
    SynonymExpander,
)
from src.retrieval.understanding.intent import (
    IntentClassifier,
)
from src.retrieval.understanding.preprocess import (
    QueryPreprocessor,
)
from src.retrieval.understanding.rewrite import (
    LLMQueryRewriter,
    QueryRewriteProvider,
    SimpleQueryRewriter,
)

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
