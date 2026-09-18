# Changelog

All notable changes to the **Medici** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] – 2026-09-18

### Added
- RAG evaluation framework (`medici-eval` CLI entry-point)
- Treant package integration for document parsing

### Removed
- PostgreSQL knowledge graph (replaced by vector-only retrieval)

### Fixed
- System prompt & token count accuracy
- Mid-stream LLM fallback reliability

---

## [0.4.0] – 2026-08-15

### Added
- Library packaging & installable `medici` package (PR #1)
- Windows platform configuration support
- NVIDIA LLM provider
- Adaptive retrieval configuration
- Faithfulness checker for generated responses
- Conversational query category routing
- Dead-letter queue in ingestion pipeline
- SSE streaming for real-time responses
- Rate limiter middleware
- Semantic chunker strategy
- Structured JSON output formatting
- PostgreSQL knowledge graph (experimental, later removed)

### Changed
- Improved reranker scoring & configuration
- Updated graph state management
- Updated response UI layout

### Fixed
- Short-term session memory bug
- Stale chunk cleanup in Qdrant
- Circular import errors in library layout
- Knowledge graph query performance
- Project metadata & layout restructuring

---

## [0.3.0] – 2026-06-01

### Added
- Multi-hop retrieval loop for complex queries
- Docling parsing by page ranges
- Batch embedding & image chunk support
- Sentence boundary detection for chunking
- LLM fallback chain (primary → secondary provider)
- LLM evaluation suite (faithfulness, relevancy)
- Parent-window context enrichment strategy
- System role separation (planner vs. executor)
- Authentication & JWT-based authorization
- Docker & Docker Compose deployment
- GitHub Actions CI pipeline

### Changed
- Updated citation function & short-term memory handling
- Updated auth & CI workflow

### Fixed
- Docker configuration issues
- Factual query routing
- Embedding cache invalidation
- Ingestion CLI stability
- Conversational history tracking
- Grader refinement & Cerebras LLM compatibility

---

## [0.2.0] – 2026-03-15

### Added
- Streamlit web UI with document upload
- Recursive character chunker
- Chunker factory for pluggable strategies
- Citation enforcer & token budget guard
- Cerebras LLM provider
- Prompt firewall & Qdrant retry logic
- Batch parsing for multi-document ingestion
- Token guard for context-window management
- Content hash for document cache deduplication
- Semantic & embedded cache layers

### Changed
- Updated LLM base class interface
- Updated hybrid search & bootstrap sparse index
- Updated graph edge routing & Qdrant search
- Updated Docling parser & multimodal item wiring
- Narrowing retry in Qdrant & base LLM

### Fixed
- Factory chunking method dispatch
- Retrieval grader scoring
- Sparse index retrieval
- Qdrant hybrid search fusion
- HTML converter & upload path handling
- Reranker mapping & parser table row extraction

---

## [0.1.0] – 2026-01-10

### Added
- Initial document ingestion pipeline (parser → chunker → embedder → store)
- Hybrid search (dense + sparse) with Qdrant vector store
- BM25 + cross-encoder re-ranker
- Agentic RAG pipeline with LangGraph orchestration
- Multi-turn conversational agent with short-term memory
- Docling document parser with test suite
- Vertex AI & Google GenAI LLM support
- Document cache & storage methods
- FastAPI server with REST routes
- Tokenizer utilities
- Conditional routing edges in retrieval graph
- Splitter-based chunking method
- README & project documentation

### Fixed
- Pipeline error handling
- LangGraph state transitions

---

[Unreleased]: https://github.com/manoje8/medici/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/manoje8/medici/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/manoje8/medici/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/manoje8/medici/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/manoje8/medici/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/manoje8/medici/releases/tag/v0.1.0
