# x-GuanHai 检索流水线文档

本文档详细描述 x-GuanHai 项目中三阶段检索流水线的设计、算法原理和使用方法。

## 目录

- [概述](#概述)
- [架构设计](#架构设计)
- [Stage 1: 查询理解](#stage-1-查询理解)
- [Stage 2: 候选召回](#stage-2-候选召回)
- [Stage 3: 排序筛选](#stage-3-排序筛选)
- [使用指南](#使用指南)
- [自定义 Provider](#自定义-provider)
- [最佳实践](#最佳实践)

---

## 概述

检索是 RAG（检索增强生成）系统的核心组件。x-GuanHai 实现了一个**三阶段检索流水线**，采用可插拔的 Provider 架构，支持灵活配置和扩展。

### 设计目标

1. **模块化**：每个阶段职责单一，可独立测试和替换
2. **可扩展**：通过 Provider 机制支持多种算法
3. **可配置**：运行时动态调整策略参数
4. **高性能**：支持批量处理和并行执行

---

## 架构设计

### 流水线架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户查询 (Query)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Stage 1: 查询理解 (Query Understanding)  — 并行执行 → merge 合并           │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐│
│  │QueryPreproc   │  │IntentClassifier│ │EntityExtractor│  │SynonymExpand││
│  │  (预处理)     │  │  (意图识别)    │  │  (实体抽取)   │  │(同义词扩展) ││
│  └───────────────┘  └───────────────┘  └───────────────┘  └─────────────┘│
│  ┌─────────────┐                                                              │
│  │SimpleRewrite│                                                              │
│  │(规则重写)    │                                                              │
│  └─────────────┘                                                              │
│                                      │                                     │
│                                      ▼ merge()                              │
│                      ┌───────────────────────────────────────┐             │
│                      │   QueryUnderstandingResult           │             │
│                      │  • processed_query (处理后的查询)   │             │
│                      │  • intent (查询意图类型)            │             │
│                      │  • entities (抽取的实体)            │             │
│                      │  • expanded_terms (扩展词)           │             │
│                      │  • sub_queries (子查询列表)          │             │
│                      └───────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Stage 2: 候选召回 (Candidate Retrieval)  — 多路并行 → 去重合并             │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐           │
│  │ ChromaVectorRetrieval      │  │  BM25RetrievalProvider      │           │
│  │    (稠密向量 ANN 检索)    │  │    (稀疏 BM25 关键词检索)   │           │
│  └─────────────────────────────┘  └─────────────────────────────┘           │
│                                      │                                     │
│                                      ▼ dedup()                             │
│                      ┌───────────────────────────────────────┐             │
│                      │   候选文档集合 (去重合并)            │             │
│                      └───────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Stage 3: 排序筛选 (Ranking & Filtering)  — 依次执行                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                        │
│  │RRFReranker │→ │MMRReranker │→ │ScoreFilter │                        │
│  │ (多路排名融合)│  │ (多样性重排) │  │ (阈值过滤)  │                        │
│  └─────────────┘  └─────────────┘  └─────────────┘                        │
│                                      │                                     │
│                                      ▼                                     │
│                      ┌───────────────────────────────────────┐             │
│                      │   最终 Top-K 检索结果               │             │
│                      └───────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              增强 → 生成                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 代码结构

```
retrieval/
├── pipeline.py              # 流水线编排器
├── understanding/
│   ├── base.py            # 查询理解抽象基类 + QueryUnderstandingResult
│   ├── preprocess.py      # 查询预处理（归一化/去停用词/标点处理）
│   ├── intent.py          # 意图识别（7 种意图类型，基于规则）
│   ├── entity.py          # 实体抽取（NER，正则 + 词典双模式）
│   ├── rewrite.py         # 查询重写（SimpleQueryRewriter / LLMQueryRewriter）
│   └── expansion.py       # 查询扩展（SynonymExpander / EmbeddingExpander）
├── candidate/
│   ├── base.py            # 候选召回抽象基类
│   ├── vector_retrieval.py # 向量检索（Chroma ANN）
│   ├── keyword_retrieval.py # 关键词检索抽象基类
│   └── bm25_retrieval.py   # BM25 稀疏检索
└── ranking/
    ├── base.py            # 排序抽象基类
    ├── mmr.py             # MMR 多样性重排
    ├── rrf.py             # RRF 排名融合
    ├── semantic.py         # 语义重排（LLM）
    └── score_filter.py    # 阈值过滤
```

---

## Stage 1: 查询理解

### 设计理念

查询理解是检索系统的"大脑"，负责将用户的原始查询转换为更精确、更丰富的检索表达。每个 Provider 并行执行，结果通过 `merge()` 合并。

### 查询理解结果

```python
@dataclass
class QueryUnderstandingResult:
    original_query: str          # 原始查询
    processed_query: str          # 处理后的查询
    intent: str | None           # 查询意图类型
    sub_queries: list[str]       # 子查询列表
    hypothetical_doc: str | None  # HyDE 假设文档（已废弃）
    expanded_terms: list[str]     # 扩展词列表
    metadata: dict[str, Any]      # 附加元数据（intent_meta / entity_meta / preprocess_meta）
```

### 提供的 Provider

#### 1. QueryPreprocessor (查询预处理)

对原始查询做归一化处理，为后续阶段提供干净的输入。

**功能**：
- 自定义正则替换
- 去除标点符号
- 大小写归一化（对英文生效）
- 停用词过滤
- 空白符归一化

**代码示例**：

```python
from retrieval.understanding.preprocess import QueryPreprocessor

provider = QueryPreprocessor(
    lowercase=True,
    remove_punctuation=False,
    stopwords={"的", "了", "在"},
)

result = provider.process("查询   RAG  技术的   原理是什么")
# result.processed_query: "查询 rag 技术 原理 是什么"
```

#### 2. IntentClassifier (意图识别)

基于正则模式识别用户查询的意图类型，支撑下游检索路由决策。

**支持的意图类型**（定义于 `constants/understanding.py`）：

| 意图 | 说明 | 示例 |
|------|------|------|
| `factual` | 事实型 | "谁在 2020 年发明了 X" |
| `opinion` | 观点型 | "对 X 的评价如何" |
| `list` | 列表型 | "列出 X 的组成部分" |
| `definition` | 定义型 | "什么是 X" |
| `comparison` | 比较型 | "X 和 Y 的区别" |
| `causal` | 因果型 | "为什么 / 结果是" |
| `howto` | 操作型 | "如何做 X" |
| `unknown` | 未知 | 未匹配到任何模式 |

**代码示例**：

```python
from retrieval.understanding.intent import IntentClassifier

provider = IntentClassifier()
result = provider.process("RAG 和 Agent 的区别是什么")

# result.intent: "comparison"
# result.metadata["intent_meta"]["confidence"]: 0.9
# result.metadata["intent_meta"]["matched_patterns"]: [...]
```

#### 3. EntityExtractor (实体抽取)

基于正则和自定义词典抽取查询中的命名实体。

**支持的实体类型**（定义于 `constants/understanding.py`）：

| 实体类型 | 说明 | 示例 |
|----------|------|------|
| `PERSON` | 人名 | — |
| `LOCATION` | 地名 | 中国、美国 |
| `ORG` | 组织/公司 | — |
| `TIME` | 时间表达式 | 2024年、今天 |
| `NUMBER` | 数字/金额 | 100元、50% |
| `TECH` | 技术术语 | Python、RAG |
| `PRODUCT` | 产品名 | — |

**代码示例**：

```python
from retrieval.understanding.entity import EntityExtractor, EntityType

provider = EntityExtractor(
    custom_entity_dict={
        EntityType.TECH: {"RAG", "LLM", "Embedding", "BGE-M3"},
    }
)
result = provider.process("2024年 RAG 技术有哪些进展")

# result.metadata["entity_meta"]["entities"] 包含：
# [{"text": "2024年", "type": "TIME", ...},
#  {"text": "RAG", "type": "TECH", ...}]
```

#### 4. SynonymExpander (同义词扩展)

基于同义词词典扩展查询词，增加召回。

```python
from retrieval.understanding.expansion import SynonymExpander

provider = SynonymExpander()
result = provider.process("RAG 的原理")
# expanded_terms 包含 ["retrieval-augmented-generation", ...]
```

#### 5. EmbeddingExpander (向量扩展)

使用 Embedding 模型在向量空间中查找语义相似的词。

```python
from retrieval.understanding.expansion import EmbeddingExpander

provider = EmbeddingExpander(embedding_model=embedding_model)
result = provider.process("RAG 技术")
# expanded_terms 包含语义相似词
```

#### 6. SimpleQueryRewriter (规则重写)

基于规则的重写，无需 LLM 调用。

```python
from retrieval.understanding.rewrite import SimpleQueryRewriter

provider = SimpleQueryRewriter()
result = provider.process("RAG 技术是什么")
# processed_query 经过规则规范化
```

#### 7. LLMQueryRewriter (LLM 重写)

使用 LLM 进行语义级别的重写。

```python
from retrieval.understanding.rewrite import LLMQueryRewriter

provider = LLMQueryRewriter(provider_name="deepseek")
result = provider.process("RAG 技术是什么")
```

### 结果合并

并行执行多个 Provider 后，使用 `merge()` 方法合并结果：

```python
merged = result1.merge(result2)
# processed_query: 取最长的（信息量最丰富）
# sub_queries: 并集去重
# expanded_terms: 并集去重
# intent: 取第一个非空的
# hypothetical_doc: 用换行合并（已废弃）
# metadata: 合并两个 dict
```

---

## Stage 2: 候选召回

### 设计理念

候选召回是检索系统的"引擎"，负责从向量数据库和索引中快速召回候选文档。Stage 2 支持多路并行召回，取长补短。

### 向量检索原理

```
查询向量 ──ANN 索引──→ Top-K 最近邻
                        │
                        ├── 优点：语义相似度高
                        └── 缺点：可能遗漏字面相关
```

### 提供的 Provider

#### 1. ChromaVectorRetrieval (向量检索)

基于 Chroma 的 ANN 检索：

```python
from retrieval.candidate.vector_retrieval import ChromaVectorRetrieval

provider = ChromaVectorRetrieval(
    vector_repo=vector_repo,
    embedding_model=embedding_model,
    top_k=10,
)
```

**支持的度量方式**（定义于 `constants/rag.py`）：
- `cosine`: 余弦相似度
- `euclidean`: 欧氏距离
- `dot`: 点积

#### 2. BM25RetrievalProvider (关键词检索)

基于 BM25 的传统关键词检索：

```python
from retrieval.candidate.bm25_retrieval import BM25RetrievalProvider

provider = BM25RetrievalProvider(
    bm25_repo=bm25_repo,
    top_k=10,
)
```

**BM25 公式**：

$$
\text{score}(D, Q) = \sum_{i=1}^{n} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot (1 - b + b \cdot \frac{|D|}{\text{avgdl}})}
$$

其中：
- $f(q_i, D)$: 词 $q_i$ 在文档 $D$ 中的频率
- $|D|$: 文档 $D$ 的长度
- $\text{avgdl}$: 平均文档长度
- $k_1$, $b$: 可调参数

### 多路召回

Stage 2 支持多路并行召回，然后去重合并：

```python
# 流水线配置
pipeline = RetrievalPipeline(
    candidate_providers=[
        ChromaVectorRetrieval(),
        BM25RetrievalProvider(),
    ],
)

# 执行时：
# 1. 并行执行两个检索器
# 2. 合并结果并按 score 排序
# 3. 去重（相同 ID 只保留一个）
```

---

## Stage 3: 排序筛选

### 设计理念

排序筛选是检索系统的"裁判"，负责从候选文档中选出最相关的结果。Stage 3 按顺序执行多个排序器。

### 提供的 Provider

#### 1. RRFReranker (RRF 排名融合)

融合多个排名列表，兼顾各路召回的优势。

**公式**：

$$
\text{RRF} = \sum_{i=1}^{k} \frac{1}{r_i + c}
$$

其中：
- $r_i$: 文档在第 $i$ 个列表中的排名
- $c$: 常数（默认 60）

```python
from retrieval.ranking.rrf import RRFReranker

provider = RRFReranker(k=60)
```

#### 2. MMRReranker (MMR 多样性重排)

平衡相关性与多样性，避免结果重复。

**公式**：

$$
\text{MMR} = \arg\max_{D_i \in R \setminus S} \left[
    \lambda \cdot \text{Sim}(D_i, Q) - (1 - \lambda) \cdot \max_{D_j \in S} \text{Sim}(D_i, D_j)
\right]
$$

其中：
- $Q$: 查询
- $R$: 候选集合
- $S$: 已选择集合
- $\lambda$: 权衡参数

**参数说明**：
- `lambda_param`:
  - `1.0`: 完全相关性优先
  - `0.5`: 平衡
  - `0.0`: 完全多样性优先

```python
from retrieval.ranking.mmr import MMRReranker
from utils.similarity import DistanceType

provider = MMRReranker(distance_type=DistanceType.COSINE)
```

#### 3. SemanticReranker (语义重排)

使用 LLM 进行语义相关性评分：

```python
from retrieval.ranking.semantic import LLMSemanticReranker

provider = LLMSemanticReranker(provider_name="deepseek")
```

#### 4. ScoreFilter (分值过滤)

基于阈值的简单过滤：

```python
from retrieval.ranking.score_filter import ScoreFilter

provider = ScoreFilter(threshold=0.7)
```

### 排序流水线

Stage 3 支持链式调用多个排序器。**注意顺序**：RRF 先融合多路结果，MMR 后做多样性重排。

```python
pipeline = RetrievalPipeline(
    reranking_providers=[
        RRFReranker(k=60),                             # 1. 先 RRF 融合
        MMRReranker(distance_type=DistanceType.COSINE), # 2. 后 MMR 多样性
    ],
    filter_providers=[
        ScoreFilter(threshold=0.7),                    # 3. 最后阈值过滤
    ],
)
```

---

## 使用指南

### 基础用法

```python
from retrieval.pipeline import RetrievalPipeline
from retrieval.understanding.preprocess import QueryPreprocessor
from retrieval.understanding.intent import IntentClassifier
from retrieval.understanding.entity import EntityExtractor
from retrieval.understanding.expansion import SynonymExpander
from retrieval.candidate.vector_retrieval import ChromaVectorRetrieval
from retrieval.candidate.bm25_retrieval import BM25RetrievalProvider
from retrieval.ranking.rrf import RRFReranker
from retrieval.ranking.mmr import MMRReranker
from retrieval.ranking.score_filter import ScoreFilter
from utils.similarity import SimilaritySearchEngine, DistanceType

# 创建流水线
pipeline = RetrievalPipeline(
    understanding_providers=[
        QueryPreprocessor(),    # 预处理：归一化、去停用词
        IntentClassifier(),     # 意图识别：识别 7 种意图类型
        EntityExtractor(),      # 实体抽取：NER
        SynonymExpander(),      # 同义词扩展
    ],
    candidate_providers=[
        ChromaVectorRetrieval(),         # 稠密向量检索
        BM25RetrievalProvider(),         # 稀疏 BM25 检索
    ],
    reranking_providers=[
        RRFReranker(k=60),                                # RRF 多路排名融合
        MMRReranker(distance_type=DistanceType.COSINE),    # MMR 多样性重排
    ],
    filter_providers=[
        ScoreFilter(threshold=0.7),
    ],
    similarity_engine=SimilaritySearchEngine(distance_type=DistanceType.COSINE),
    default_top_k=5,
    default_threshold=0.7,
)

# 初始化
pipeline.initialize()

# 执行检索
results = pipeline.retrieve(
    query="RAG 技术的原理是什么",
    top_k=5,
)

# results 为 RetrievalResult，包含：
# - documents: 检索到的文档列表
# - metadata: 检索过程的元信息
```

### 高级用法

```python
# 动态添加 Provider
pipeline.add_understanding_provider(SynonymExpander())
pipeline.add_candidate_provider(BM25RetrievalProvider(bm25_repo=bm25_repo))

# 获取统计信息
stats = pipeline.get_stats()
print(stats)
# {
#     "type": "retrieval_pipeline",
#     "stages": {
#         "understanding": ["query_preprocessor", "intent_classifier",
#                           "entity_extractor", "synonym_expander"],
#         "candidate": ["chroma_vector", "bm25_keyword"],
#         "reranking": ["rrf_reranker", "mmr_reranker"]
#     },
#     "defaults": {"top_k": 5, "threshold": 0.7}
# }
```

---

## 自定义 Provider

### 自定义查询理解 Provider

```python
from retrieval.understanding.base import (
    BaseQueryUnderstandingProvider,
    QueryUnderstandingResult
)

class MyQueryPreprocessor(BaseQueryUnderstandingProvider):
    name = "my_preprocessor"
    description = "自定义查询预处理"

    def process(self, query: str, context=None) -> QueryUnderstandingResult:
        return QueryUnderstandingResult(
            original_query=query,
            processed_query=query.strip(),
        )

    def supports(self) -> list[str]:
        return ["preprocess"]
```

### 自定义候选召回 Provider

```python
from retrieval.candidate.base import BaseRetrievalProvider

class MyVectorRetrieval(BaseRetrievalProvider):
    name = "my_vector"
    description = "自定义向量检索"

    @property
    def vector_store(self):
        return self._vector_store

    @property
    def embedding_model(self):
        return self._embedding_model

    def __init__(self, vector_store, embedding_model):
        self._vector_store = vector_store
        self._embedding_model = embedding_model

    def search(self, query, top_k=10, **kwargs):
        # 实现检索逻辑
        return []
```

### 自定义排序 Provider

```python
from retrieval.ranking.base import BaseRerankingProvider

class MyReranker(BaseRerankingProvider):
    name = "my_reranker"
    description = "自定义排序"

    def rerank(self, query, candidates, **kwargs):
        # 实现排序逻辑
        return candidates
```

### 注册自定义 Provider

```python
# 创建流水线时注入
pipeline = RetrievalPipeline(
    understanding_providers=[MyQueryPreprocessor()],
    candidate_providers=[MyVectorRetrieval(...)],
    reranking_providers=[MyReranker()],
)
```

---

## 最佳实践

### 1. 选择合适的 Provider 组合

| 场景 | 推荐配置 |
|------|----------|
| 通用问答 | QueryPreprocessor → IntentClassifier → EntityExtractor → SynonymExpander → ChromaVector + BM25 → RRF + MMR |
| 精确搜索 | QueryPreprocessor → BM25 → ScoreFilter |
| 学术问答 | QueryPreprocessor → IntentClassifier → EntityExtractor → SynonymExpander → EmbeddingExpander → Chroma + BM25 → RRF + MMR + SemanticReranker |

### 2. 参数调优

```python
# MMR 参数
results = pipeline.retrieve(
    query="...",
    mmr_lambda=0.7,  # 提高相关性权重
)

# 阈值参数
results = pipeline.retrieve(
    query="...",
    similarity_threshold=0.8,  # 提高精度
)

# Top-K 参数
results = pipeline.retrieve(
    query="...",
    top_k=10,  # 召回更多候选
)
```

### 3. 意图识别路由示例

```python
result = IntentClassifier().process(query)

if result.intent == "comparison":
    # 比较类查询：增加 BM25 权重（字面匹配更重要）
    pipeline = RetrievalPipeline(
        candidate_providers=[BM25RetrievalProvider(), ChromaVectorRetrieval()],
        ...
    )
elif result.intent == "definition":
    # 定义类查询：增加向量检索权重（语义理解更重要）
    pipeline = RetrievalPipeline(
        candidate_providers=[ChromaVectorRetrieval(), BM25RetrievalProvider()],
        ...
    )
```

### 4. 监控和调优

```python
# 获取统计信息
stats = pipeline.get_stats()
print(f"检索结果数: {len(results.documents)}")
print(f"各阶段 Provider: {stats['stages']}")
```

---

## 相关文档

- [架构设计文档](architecture.md) - 整体架构说明
