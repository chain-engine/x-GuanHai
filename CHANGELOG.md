# x-GuanHai Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `SemanticSplitter` implementation with embedding-based semantic chunking
- Thread-safe caching in `CachedBGEEmbeddingModel` using `threading.RLock`
- Pagination support in `IndexingService.list_documents()`
- SHA256 hashing for cache keys instead of MD5

### Fixed
- Test import paths matching actual source directory structure
- Configuration consistency between `config.yaml` and `.env.example`
- CORS security by restricting allowed origins
- Error handling in `JSONDocumentStore.load()` and `list_all()`
- `VectorStore.get_count()` now raises exceptions instead of returning 0

### Changed
- Default embedding device changed from `cuda` to `cpu` in config.yaml
- Default generation provider changed from `openai` to `deepseek`
- `list_documents()` now returns pagination metadata

### Security
- CORS origins now explicitly listed instead of wildcard

## [0.2.0] - 2024-07-20

### Added
- Initial release with RAG functionality
- Multiple text splitting strategies (Character, Word, Sentence, Paragraph, Semantic)
- BGE-M3 embedding model support
- Chroma vector store integration
- FastAPI REST API endpoints
- JSON document storage
- MMR (Maximal Marginal Relevance) reranking

### Features
- Document upload and indexing
- Semantic search retrieval
- RAG query with context-augmented generation
- Multiple LLM provider support (OpenAI, DeepSeek)
- Rate limiting
- Health check endpoints
