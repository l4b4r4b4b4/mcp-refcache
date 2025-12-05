# Embeddings Feature - Future Vision

## Status: PLANNED (v0.1.0+)

This document captures the vision for embedding-based features in mcp-refcache.
These features are **not** part of the current implementation scope.

---

## Overview

Embeddings could unlock powerful semantic capabilities on top of the reference-based caching system:

- **Semantic cache lookup** - Find cached values by meaning, not just exact keys
- **Relevance-based previews** - Sample the most relevant items, not just evenly-spaced
- **Tool result composition** - Find which cached results are relevant to combine
- **Deduplication** - Detect semantically similar cached entries

---

## Proposed Architecture

### Embedder Protocol

```python
from typing import Protocol


class Embedder(Protocol):
    """Protocol for embedding adapters."""
    
    @property
    def model_name(self) -> str:
        """The embedding model name."""
        ...
    
    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        ...
    
    def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        ...
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently."""
        ...
```

### Adapter Implementations

```
┌─────────────────────────────────────────────────────────────┐
│                     Embedder (Protocol)                     │
│  embed(text) -> list[float]                                 │
│  embed_batch(texts) -> list[list[float]]                    │
│  dimension: int                                             │
└─────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ SentenceTransf. │ │ OpenAIEmbedding │ │ CohereEmbedding │
│ (local, free)   │ │ (API, paid)     │ │ (API, paid)     │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ all-MiniLM-L6   │ │ text-embed-3    │ │ embed-v3        │
│ bge-large-en    │ │ text-embed-ada  │ │ embed-english   │
│ gte-base        │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

#### SentenceTransformerAdapter

```python
class SentenceTransformerAdapter:
    """Adapter for sentence-transformers library (local models)."""
    
    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        self._model_name = model
        self._model: SentenceTransformer | None = None  # Lazy load
    
    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            # Models cached to ~/.cache/huggingface/hub/
            self._model = SentenceTransformer(self._model_name)
        return self._model
    
    @property
    def dimension(self) -> int:
        return self._get_model().get_sentence_embedding_dimension()
    
    def embed(self, text: str) -> list[float]:
        return self._get_model().encode(text).tolist()
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._get_model().encode(texts).tolist()
```

#### OpenAIEmbeddingAdapter

```python
class OpenAIEmbeddingAdapter:
    """Adapter for OpenAI embedding API."""
    
    DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    
    def __init__(
        self, 
        model: str = "text-embedding-3-small",
        api_key: str | None = None,  # Falls back to OPENAI_API_KEY env
    ):
        self._model_name = model
        self._api_key = api_key
        self._client: openai.OpenAI | None = None
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._get_client().embeddings.create(
            model=self._model_name,
            input=texts,
        )
        return [item.embedding for item in response.data]
```

---

## Use Cases

### 1. Semantic Cache Lookup

Find cached values by meaning instead of exact key matching:

```python
from mcp_refcache import SemanticCache
from mcp_refcache.embeddings import SentenceTransformerAdapter

embedder = SentenceTransformerAdapter("all-MiniLM-L6-v2")
cache = SemanticCache(embedder=embedder)

# Store with semantic indexing
cache.set("user_prefs", {"theme": "dark", "language": "en"})
cache.set("order_history", [...])

# Search by meaning
results = cache.search("what does the customer like?")
# Returns: [CacheReference(key="user_prefs", similarity=0.87)]
```

### 2. Relevance-Based Preview (Smart Sampling)

Instead of evenly-spaced sampling, select the most relevant items:

```python
# Current behavior: Sample items at positions 0, 100, 200, 300...
preview = cache.get(ref_id)  # Dumb positional sampling

# With embeddings: Sample items most relevant to query
preview = cache.get(
    ref_id, 
    query="machine learning papers",
    preview_strategy=PreviewStrategy.RELEVANCE,
)
# Returns the 10 most relevant items from 10,000 cached papers
```

#### RelevancePreviewGenerator

```python
class RelevancePreviewGenerator(PreviewGenerator):
    """Sample items by semantic relevance, not position."""
    
    def __init__(self, embedder: Embedder):
        self._embedder = embedder
    
    def generate(
        self,
        value: Any,
        max_size: int,
        measurer: SizeMeasurer,
        query: str | None = None,
        **kwargs,
    ) -> PreviewResult:
        if query is None or not isinstance(value, (list, dict)):
            # Fall back to standard sampling
            return SampleGenerator().generate(value, max_size, measurer)
        
        # Embed query
        query_embedding = self._embedder.embed(query)
        
        # Embed items and compute similarities
        items = list(value) if isinstance(value, list) else list(value.items())
        item_texts = [json.dumps(item, default=str) for item in items]
        item_embeddings = self._embedder.embed_batch(item_texts)
        
        similarities = [
            cosine_similarity(query_embedding, emb) 
            for emb in item_embeddings
        ]
        
        # Select top-k most relevant
        ranked_indices = sorted(
            range(len(items)), 
            key=lambda i: similarities[i], 
            reverse=True
        )
        
        # Take items until we hit size limit
        selected = []
        for idx in ranked_indices:
            candidate = selected + [items[idx]]
            if measurer.measure(candidate) > max_size:
                break
            selected.append(items[idx])
        
        return PreviewResult(
            preview=selected,
            strategy=PreviewStrategy.RELEVANCE,
            ...
        )
```

### 3. Tool Result Composition

When multiple tools cache results, find relevant ones for the current task:

```python
# Tool A caches search results → ref_a
# Tool B caches database query → ref_b  
# Tool C caches API response → ref_c

# Find which cached results are relevant to current task
relevant_refs = cache.find_relevant(
    query="user's recent purchases",
    refs=[ref_a, ref_b, ref_c],
    threshold=0.7,  # Minimum similarity
)
# Returns: [ref_b]  (database had purchase data)
```

### 4. Semantic Deduplication

Detect when caching semantically similar values:

```python
cache.set("greeting_v1", {"message": "Hello world"})

# Warn about similar existing entry
cache.set("greeting_v2", {"message": "Hello, world!"}, dedupe=True)
# Warning: Similar to existing entry 'greeting_v1' (0.98 similarity)
# Option: dedupe="error" | "warn" | "skip" | "allow"
```

### 5. Hierarchical Retrieval for Massive Collections

Two-stage retrieval for very large cached collections:

```python
# 100,000 documents cached under one reference
ref = cache.set("corpus", documents)

# Stage 1: Embedding search finds top 100 relevant
# Stage 2: Return paginated preview of those 100
response = cache.get(
    ref.ref_id,
    query="climate change impacts",
    page=1,
    page_size=20,
)
# Returns: 20 most relevant docs (of top 100) with pagination
```

---

## Vector Storage Options

For semantic search, we need vector indexing. Our tiered approach:

### Tier 1: ChromaDB In-Memory (Default)

```python
# Simple, no external dependencies, good for most use cases
from mcp_refcache.embeddings import ChromaIndex

index = ChromaIndex()  # In-memory by default
cache = SemanticCache(embedder=embedder, index=index)
```

| Pros | Cons |
|------|------|
| Zero setup, batteries included | Limited filter options (no SQL) |
| Persistence option available | Memory-bound for large collections |
| Simple Python API | |

### Tier 2: SQLite + pgvector + HNSW (Power Users)

For users needing SQL filtering or larger scale:

```python
# SQLite for local, pgvector for production
from mcp_refcache.embeddings import SQLiteVectorIndex, PgVectorIndex

# Local development
index = SQLiteVectorIndex("cache.db", hnsw=True)

# Production (PostgreSQL + pgvector)
index = PgVectorIndex(connection_string, hnsw=True)
```

| Pros | Cons |
|------|------|
| Full SQL filtering | More setup required |
| Scales to millions of vectors | External DB dependency (pgvector) |
| HNSW for fast ANN search | |
| Battle-tested persistence | |

### Tier 3: External ChromaDB Server (Enterprise)

For distributed/multi-process scenarios:

```python
from mcp_refcache.embeddings import ChromaIndex

index = ChromaIndex(
    host="chroma.internal.company.com",
    port=8000,
)
```

| Pros | Cons |
|------|------|
| Horizontal scaling | Operational overhead |
| Shared across services | Network latency |
| Managed persistence | Another service to maintain |

### Protocol Design

```python
class VectorIndex(Protocol):
    """Protocol for vector storage backends."""
    
    def add(self, id: str, embedding: list[float], metadata: dict) -> None: ...
    def search(
        self, 
        embedding: list[float], 
        top_k: int,
        filter: dict | None = None,  # Backend-specific filtering
    ) -> list[SearchResult]: ...
    def delete(self, id: str) -> None: ...
    def clear(self) -> None: ...


class ChromaIndex:
    """ChromaDB-backed index. Default choice."""
    
    def __init__(
        self,
        collection_name: str = "mcp_refcache",
        persist_directory: str | None = None,  # None = in-memory
        host: str | None = None,  # For external server
        port: int = 8000,
    ): ...


class SQLiteVectorIndex:
    """SQLite with vector extension. Good for SQL filtering needs."""
    
    def __init__(
        self,
        db_path: str = ":memory:",
        hnsw: bool = True,  # Use HNSW index for ANN
    ): ...


class PgVectorIndex:
    """PostgreSQL + pgvector. Production-grade scaling."""
    
    def __init__(
        self,
        connection_string: str,
        table_name: str = "mcp_refcache_vectors",
        hnsw: bool = True,
    ): ...
```

---

## pyproject.toml Changes (Future)

```toml
[project.optional-dependencies]
# Existing
tiktoken = ["tiktoken>=0.5.0"]
transformers = ["transformers>=4.30.0"]

# Embedding adapters
embeddings = [
    "sentence-transformers>=2.2.0",
    "numpy>=1.24.0",
]
embeddings-openai = [
    "openai>=1.0.0",
]

# Vector storage backends
chromadb = [
    "chromadb>=0.4.0",
]
sqlite-vec = [
    "sqlite-vec>=0.1.0",  # SQLite vector extension
]
pgvector = [
    "pgvector>=0.2.0",
    "psycopg[binary]>=3.1.0",
]

# Convenience bundles
embeddings-local = [
    "mcp-refcache[embeddings,chromadb]",
]
embeddings-postgres = [
    "mcp-refcache[embeddings,pgvector]",
]

# Updated 'all' extra
all = [
    "mcp-refcache[redis,mcp,tiktoken,transformers,embeddings,chromadb]",
]
```

---

## Implementation Roadmap

| Version | Features |
|---------|----------|
| **v0.0.1** | Core caching, token counting (tiktoken + HF) |
| **v0.1.0** | Embedder protocol, SentenceTransformerAdapter, ChromaDB in-memory |
| **v0.2.0** | RelevancePreviewGenerator, basic `cache.search()` |
| **v0.3.0** | SQLite + HNSW, pgvector support, deduplication |
| **v0.4.0** | OpenAI/Cohere adapters, external ChromaDB server |
| **v0.5.0** | Tool result composition, hierarchical retrieval |

---

## Open Questions

1. **Index persistence** - Should vector indices be persisted alongside the cache backend? Or separate concern?
   - *Leaning*: Separate concern. Cache backend handles values, VectorIndex handles embeddings.

2. **Embedding caching** - Should we cache embeddings of cached values? (Avoids re-embedding on every search)
   - *Leaning*: Yes, store embeddings in VectorIndex metadata or separate table.

3. **Incremental indexing** - How to handle `cache.set()` efficiently without rebuilding entire index?
   - *Leaning*: HNSW supports incremental inserts. ChromaDB handles this natively.

4. **Multi-modal** - Should we support image/audio embeddings? (CLIP, CLAP, etc.)
   - *Leaning*: Defer to v1.0+. Text embeddings cover 90% of use cases.

5. **Hybrid search** - Combine semantic + keyword search? (BM25 + embeddings)
   - *Leaning*: SQLite/pgvector can do this. ChromaDB has `where` filters. Worth exploring.

6. **ChromaDB filter limitations** - What if users need complex SQL that ChromaDB can't express?
   - *Answer*: Graduate to SQLite or pgvector tier. Clear upgrade path.

---

## References

- [Sentence Transformers](https://www.sbert.net/)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [FAISS](https://github.com/facebookresearch/faiss)
- [ChromaDB](https://www.trychroma.com/)
- [LanceDB](https://lancedb.com/)

---

## Session Log

### Initial Planning (Current Session)
- Discussed sentence-transformer tokenizers (not needed for token counting)
- Identified embedding use cases for future versions
- Created this feature scratchpad
- Decision: Defer to v0.1.0+, focus on token counting for v0.0.1