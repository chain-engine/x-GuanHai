#!/usr/bin/env python3
"""
Constants Module

项目全部常量定义（不含枚举，枚举定义见 enums.py）。
默认值统一从本模块引用，避免魔法数值和硬编码字符串。
"""

from typing import Final

from src.constants.enums import DocType, EntityType, IntentType

# ====================================
# 配置文件
# ====================================
DEFAULT_CONFIG_FILE: str = "config.yaml"

# ====================================
# 应用信息
# ====================================
APP_ID: str = "x-GuanHai"
APP_NAME: str = "观海（GuanHai）"
APP_DESCRIPTION: str = "一个支持 HTTP 与 MCP 双挂载的 RAG（检索增强生成）一体化工程框架"
APP_VERSION: str = "0.1.0"
API_PREFIX: Final[str] = "/api/v1"

# ====================================
# 开放 API 认证（GuanHai-1 签名）
# ====================================
OPENAPI_HEADER_APP_ID: Final[str] = "X-App-Id"
OPENAPI_HEADER_DATE: Final[str] = "X-App-Date"
OPENAPI_HEADER_AUTHORIZATION: Final[str] = "X-App-Authorization"
OPENAPI_ALGORITHM: Final[str] = "GuanHai-1"
OPENAPI_CONTENT_TYPE: Final[str] = "application/json"
OPENAPI_SIGNATURE_WINDOW_SECONDS: Final[int] = 300

# ====================================
# 文档类型与状态
# ====================================
SUPPORTED_DOC_TYPES: Final[set[str]] = set(DocType.get_all_marks())

# ====================================
# 距离度量方式
# ====================================
DISTANCE_COSINE: Final[str] = "cosine"
DISTANCE_EUCLIDEAN: Final[str] = "euclidean"
DISTANCE_DOT: Final[str] = "dot"

# ====================================
# 检索常量
# ====================================
DEFAULT_TOP_K: Final[int] = 5
DEFAULT_SIMILARITY_THRESHOLD: Final[float] = 0.7
DEFAULT_MMR_LAMBDA: Final[float] = 0.5

# ====================================
# 提示词模板
# ====================================
DEFAULT_SYSTEM_PROMPT: Final[str] = "你是一个专业的AI助手，请根据提供的参考资料回答用户问题。"
DEFAULT_USER_PROMPT_TEMPLATE: Final[str] = """基于以下参考资料回答问题。
如果参考资料中没有相关信息，请直接说明无法回答，不要编造内容。

参考资料：
{context}

用户问题：{query}

请给出准确、简洁的回答。"""

# ====================================
# 分块常量
# ====================================
DEFAULT_CHUNK_SIZE: Final[int] = 512
DEFAULT_CHUNK_OVERLAP: Final[int] = 50

# ====================================
# 嵌入模型常量
# ====================================
DEFAULT_EMBEDDING_MODEL: Final[str] = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DEVICE: Final[str] = "cpu"
DEFAULT_EMBEDDING_BATCH_SIZE: Final[int] = 32
DEFAULT_EMBEDDING_CACHE_SIZE: Final[int] = 100

# ====================================
# 生成常量
# ====================================
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_MAX_TOKENS: Final[int] = 2000
DEFAULT_TIMEOUT: Final[int] = 30


# ====================================
# 查询理解常量
# ====================================

# 意图识别模式：(正则模式, 权重)
_IntentPattern = tuple[str, float]

INTENT_PATTERNS: Final[dict[IntentType, list[_IntentPattern]]] = {
    IntentType.FACTUAL: [
        (r"(谁|什么时间|何时|哪一年|哪个|何处|什么)", 0.8),
        (r"(出生|死亡|创立|成立|发明|发现|建于)", 0.6),
        (r"\d{4}年", 0.4),
    ],
    IntentType.OPINION: [
        (r"(觉得|认为|评价|看法|观点|意见|感觉|好不好)", 0.9),
        (r"(优缺点|优势|劣势|值得)", 0.7),
    ],
    IntentType.LIST: [
        (r"(列出|列举|有哪些|包括什么|罗列)", 0.9),
        (r"(组成部分|要素|因素|步骤|流程|特点)", 0.6),
    ],
    IntentType.DEFINITION: [
        (r"(什么是|什么叫|定义|含义|解释一下)", 0.9),
        (r"(是指|指的是|即)", 0.7),
    ],
    IntentType.COMPARISON: [
        (r"(区别|差异|不同|比较|对比)", 0.9),
        (r"(和.*哪个好|.*vs.*|.* versus .*)", 0.8),
        (r"(比.*更好|比.*优秀)", 0.6),
    ],
    IntentType.CAUSAL: [
        (r"(为什么|原因|由于|因为)", 0.9),
        (r"(导致|结果|因此|所以|致使)", 0.7),
    ],
    IntentType.HOWTO: [
        (r"(如何|怎么|怎样|如何实现|如何做)", 0.9),
        (r"(步骤|方法|教程|指南)", 0.5),
    ],
}

# 默认最低置信度
DEFAULT_INTENT_MIN_CONFIDENCE: Final[float] = 0.3

# 实体抽取模式
ENTITY_PATTERNS: Final[dict[EntityType, list[str]]] = {
    EntityType.TIME: [
        r"\d{4}年\d{1,2}月\d{1,2}日",
        r"\d{4}年\d{1,2}月",
        r"\d{4}年",
        r"(去年|今年|明年|上周|下周|今天|明天|昨天|本周|下月)",
        r"第[一二三四五六七八九十百千万\d]+[天周月年]",
        r"(世纪|年代)",
    ],
    EntityType.NUMBER: [
        r"\d+\.?\d*%",
        r"\d+\.?\d*元",
        r"\d+\.?\d*[万千百亿]|\d+\.?\d*亿",
        r"\d+",
    ],
    EntityType.LOCATION: [
        r"[A-Z\u4e00-\u9fa5]+(?:省|市|区|县|州|国)",
        r"(中国|美国|英国|德国|法国|日本|韩国|俄罗斯)",
    ],
}

# 停用词表
DEFAULT_QUERY_STOPWORDS: Final[set[str]] = {
    "的",
    "了",
    "在",
    "是",
    "我",
    "有",
    "和",
    "就",
    "不",
    "人",
    "都",
    "一",
    "一个",
    "上",
    "也",
    "很",
    "到",
    "说",
    "要",
    "去",
    "你",
    "会",
    "着",
    "没有",
    "看",
    "好",
    "自己",
    "这",
}

__all__ = [
    "DEFAULT_CONFIG_FILE",
    "APP_NAME",
    "APP_DESCRIPTION",
    "APP_VERSION",
    "API_PREFIX",
    "SUPPORTED_DOC_TYPES",
    "DISTANCE_COSINE",
    "DISTANCE_EUCLIDEAN",
    "DISTANCE_DOT",
    "DEFAULT_TOP_K",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_MMR_LAMBDA",
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_USER_PROMPT_TEMPLATE",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_EMBEDDING_DEVICE",
    "DEFAULT_EMBEDDING_BATCH_SIZE",
    "DEFAULT_EMBEDDING_CACHE_SIZE",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT",
    "INTENT_PATTERNS",
    "ENTITY_PATTERNS",
    "DEFAULT_INTENT_MIN_CONFIDENCE",
    "DEFAULT_QUERY_STOPWORDS",
]
