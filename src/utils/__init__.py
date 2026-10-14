#!/usr/bin/env python3
"""
Utils Package

工具模块，提供相似度计算、过滤和索引优化功能
"""

# 相似度计算
from src.constants import DistanceType

# 过滤器
from src.utils.filters import (
    MetadataFilterEngine,
)

# 索引优化
from src.utils.index_optimizer import (
    IndexConfig,
    MemoryEstimate,
    VectorIndexOptimizer,
)
from src.utils.similarity import (
    SimilaritySearchEngine,
)

__all__ = [
    # Similarity - 相似度计算
    "SimilaritySearchEngine",
    "DistanceType",
    # Filters - 元数据过滤
    "MetadataFilterEngine",
    # Index Optimizer - 索引优化
    "VectorIndexOptimizer",
    "IndexConfig",
    "MemoryEstimate",
]
