# x-GuanHai 架构设计文档

本文档详细描述 x-GuanHai 项目的架构设计，包括分层架构、模块设计、设计模式等内容。

## 目录

- [总体架构](#总体架构)
- [分层架构](#分层架构)
- [核心模块设计](#核心模块设计)
- [设计模式](#设计模式)
- [依赖规则](#依赖规则)

---

## 总体架构

x-GuanHai 是一个**生产级 RAG（检索增强生成）一体化工程框架**，采用五层架构 + 三阶段检索流水线的设计。

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户请求                                         │
│                    (API Gateway / CLI / SDK)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API 接口层 (api/)                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  health.py  │  │   rag.py    │  │document.py │  │    ...      │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RAG 核心层 (rag/)                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ pipeline.py│  │retrieval.py │  │augment.py  │  │generation.py│       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        检索子系统 (retrieval/)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RetrievalPipeline                                  │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │   │
│  │  │ Stage 1        │  │ Stage 2        │  │ Stage 3        │       │   │
│  │  │  查询理解       │→ │ 候选召回       │→ │ 排序筛选       │       │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           基础设施层 (infras/)                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  │
│  │ vector.py │  │  bm25.py  │  │embedding. │  │ storage.py│  │  llm.py   │  │
│  │ (Chroma)  │  │  (BM25)   │  │  (BGE-M3) │  │  (JSON)   │  │(LLM 提供) │  │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 分层架构

### 层次概览

| 层次 | 目录 | 职责 | 依赖关系 |
|------|------|------|----------|
| API 层 | `api/` | 接收请求、参数校验、路由分发 | → Service 层 |
| 业务层 | `services/` | 业务逻辑编排、事务管理 | → Repository / RAG |
| RAG 层 | `rag/` | RAG 核心流程编排 | → Retrieval / Infras |
| 检索层 | `retrieval/` | 三阶段检索流水线 | → Repository / Infras |
| 数据层 | `repositories/` | 数据访问封装 | → Infras 层 |
| 基础设施层 | `infras/` | 底层存储、模型封装 | 无业务依赖 |
| 核心支撑层 | `core/` | 配置、日志、异常、中间件 | 无业务依赖 |
| 常量层 | `constants/` | 枚举类型、模式配置 | 无业务依赖 |

### 各层职责

#### 1. API 接口层 (`api/`)

**职责**：
- 接收 HTTP 请求
- 参数校验（Pydantic Schema）
- 调用 Service 层
- 标准化返回格式

**原则**：
- 禁止直接访问 Repository 或 Infras 层
- 不包含业务逻辑

**示例**：

```python
# api/v1/rag.py
@router.post("/rag/query")
async def rag_query(
    request: RAGQueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    result = await rag_service.query(...)
    return {"code": 200, "data": result}
```

#### 2. 业务服务层 (`services/`)

**职责**：
- 封装业务逻辑
- 事务管理
- 服务编排

**示例**：

```python
# services/rag_service.py
class RAGService:
    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline

    async def query(self, query: str, ...):
        return await self.pipeline.query(query, ...)
```

#### 3. RAG 核心层 (`rag/`)

**职责**：
- 编排检索→增强→生成全流程
- 定义 RAG 标准接口

**组件**：
- `Retrieval`: 检索入口
- `Augmentation`: 上下文增强
- `Generation`: LLM 生成
- `Pipeline`: 流程编排

#### 4. 检索子系统 (`retrieval/`)

**职责**：
- 三阶段检索流水线（查询理解 → 候选召回 → 排序筛选）
- 可插拔的 Provider 机制

**数据访问**：
- `VectorRepository` → Chroma 向量存储
- `BM25Repository` → 内存倒排索引

**详见**：[检索流水线文档](retrieval-pipeline.md)

#### 5. 数据访问层 (`repositories/`)

**职责**：
- 封装数据操作
- 隐藏存储细节
- 提供统一的数据接口

**示例**：

```python
# repositories/vector_repository.py
class VectorRepository(BaseRepository):
    def search(self, query_embedding, top_k, where=None):
        # 封装 Chroma 操作
        return self._store.search(...)
```

#### 6. 基础设施层 (`infras/`)

**职责**：
- 底层存储实现
- 第三方服务封装
- 硬件/平台相关逻辑

**组件**：
- `vector.py`: 向量存储抽象基类 + Chroma 实现（后续可扩展其他向量数据库）
- `bm25.py`: BM25 稀疏索引存储
- `embedding.py`: 嵌入模型抽象基类 + BGE-M3 实现
- `storage.py`: 文档存储抽象基类 + JSON 实现
- `llm.py`: LLM 提供者抽象基类 + 多提供商实现（DeepSeek/豆包/阿里云/Mimo/Mock）

#### 7. 核心支撑层 (`core/`)

**职责**：
- 配置管理
- 日志记录
- 异常定义
- 中间件支持

**特点**：
- 不依赖任何业务层
- 可独立使用

#### 8. 常量层 (`constants/`)

**职责**：
- 集中管理所有枚举类型和模式配置
- 消除代码中的魔法字符串和魔法数字

**包含**：
- `enums.py`: 全部枚举定义（状态/类型/意图/实体等）
- `constants.py`: 全部常量定义（默认参数/模式/停用词等）
- `base.py`: 枚举基类族（BaseEnum / StrBaseEnum / IntBaseEnum / FloatBaseEnum）

```python
from constants import IntentType, EntityType, INTENT_PATTERNS
```

---

## 核心模块设计

### 1. 配置中心

三层配置优先级：

```
环境变量 > YAML 配置 > 默认值
```

```python
# core/config.py
class Settings:
    def _load_config(self):
        # 1. 加载默认值
        # 2. 合并 YAML 配置
        # 3. 合并环境变量
```

### 2. 异常体系

统一异常继承链：

```
AppException
├── BusinessError (4xx)
│   ├── NotFoundError
│   ├── ValidationError
│   └── RateLimitError
└── SystemError (5xx)
    ├── RetrievalError
    ├── GenerationError
    └── VectorStoreError
```

### 3. LLM Provider 模式

使用抽象基类 + 注册表模式：

```python
# infras/llm.py
class BaseLLMProvider(ABC):
    @abstractmethod
    def create_chat_model(self) -> BaseChatModel:
        ...

# 提供者注册表
_PROVIDER_REGISTRY = {
    "deepseek": DeepSeekProvider,
    "doubao": DoubaoProvider,
    ...
}

def get_llm_provider(name: str) -> BaseLLMProvider:
    return _PROVIDER_REGISTRY[name]()
```

### 4. 三阶段检索流水线

采用策略模式 + 责任链模式：

```python
class RetrievalPipeline:
    def __init__(
        self,
        understanding_providers: list[BaseQueryUnderstandingProvider],
        candidate_providers: list[BaseRetrievalProvider],
        reranking_providers: list[BaseRerankingProvider],
    ):
        ...
```

**详见**：[检索流水线文档](retrieval-pipeline.md)

---

## 设计模式

### 1. 工厂模式

用于创建不同类型的 Provider：

```python
# 创建切分器
splitter = create_splitter(
    strategy=SplitStrategy.SEMANTIC,
    chunk_size=512
)
```

### 2. 策略模式

检索流水线支持多种策略：

```python
# 不同重排序策略
MMRReranker()  # 多样性重排
RRFReranker()   # 排名融合
ScoreFilter()   # 阈值过滤
```

### 3. 装饰器模式

缓存装饰器：

```python
@cached(ttl=60)
def expensive_operation():
    ...
```

### 4. 模板方法模式

三层抽象基类定义骨架：

```python
# retrieval/understanding/base.py
class BaseQueryUnderstandingProvider(ABC):
    @abstractmethod
    def process(self, query, context) -> QueryUnderstandingResult:
        ...
```

---

## 依赖规则

### 允许的依赖关系

```
✅ API → Service → Repository → Infras
✅ Service/Utils → Core (配置/日志)
✅ RAG → Retrieval → Repository
✅ Repository → Infras
✅ Retrieval/Repository → Constants
```

### 禁止的依赖关系

```
❌ API → Repository (跨层)
❌ API → Infras (跨层)
❌ 下层 → 上层
❌ 循环依赖
❌ Infras → Repository (禁止反向)
```

### 依赖检查

在代码审查时应检查以下违规：

1. **跨层调用**：API 层直接调用 Repository
2. **下层依赖上层**：Infras 层导入 Service 层
3. **循环依赖**：A 导入 B，B 导入 A

---

## 扩展指南

### 添加新的 LLM Provider

1. 继承 `BaseLLMProvider`
2. 实现 `_get_default_config` 和 `create_chat_model`
3. 注册到 `_PROVIDER_REGISTRY`

```python
class NewProvider(BaseLLMProvider):
    name = "new"
    description = "New LLM Provider"

    @classmethod
    def _get_default_config(cls) -> LLMConfig:
        settings = cls._get_settings()
        return LLMConfig(
            api_key=settings.NEW_API_KEY,
            ...
        )

_PROVIDER_REGISTRY["new"] = NewProvider
```

### 添加新的检索策略

1. 在对应目录创建新文件
2. 继承对应的抽象基类
3. 实现抽象方法

```python
# retrieval/candidate/new_retrieval.py
class NewRetrievalProvider(BaseRetrievalProvider):
    name = "new_retrieval"

    def search(self, query, top_k, **kwargs):
        ...
```

### 添加新的缓存实现

使用 `LRUCache` 基类：

```python
from utils.cache import LRUCache

class MyCache(LRUCache[MyType]):
    def __init__(self):
        super().__init__(capacity=100, ttl=3600)
```

---

## 最佳实践

### 1. 模块导入规范

```python
# ✅ 正确的导入顺序
import os
import sys
from typing import TYPE_CHECKING

from core.logger import logger
from core.exceptions import AppException

if TYPE_CHECKING:
    from services import MyService
```

### 2. 类型注解规范

```python
# ✅ 始终提供返回类型
def my_function(arg: str) -> dict[str, Any]:
    ...

# ✅ 使用 Protocol 定义接口
class MyProtocol(Protocol):
    def method(self) -> str: ...
```

### 3. 异常处理规范

```python
# ✅ 记录异常日志
try:
    do_something()
except SomeError as e:
    logger.error(f"操作失败: {e}")
    raise  # 重新抛出，不要吞掉

# ✅ 使用链式异常
raise RetrievalError(f"检索失败: {e}") from e
```

### 4. 配置管理规范

```python
# ✅ 使用类型安全的配置
@dataclass
class MyConfig:
    timeout: int = 30
    retry_count: int = 3

# ✅ 从环境变量加载
import os
timeout = int(os.getenv("TIMEOUT", "30"))
```

---

## 相关文档

- [检索流水线文档](retrieval-pipeline.md) - 详细的三阶段检索算法说明
- [API 参考文档](api-reference.md) - 接口使用说明
- [配置指南](configuration.md) - 配置项详解
- [开发指南](development.md) - 开发环境配置
