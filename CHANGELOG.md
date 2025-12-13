# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- MCP template (cookiecutter/copier) for new servers with refcache
- Time series backend for financial data use cases (InfluxDB, TimescaleDB)
- Redis Cluster/Sentinel support for high availability
- Metrics/observability hooks (Prometheus, OpenTelemetry)

## [0.1.0] - 2025-01-XX

### Added

#### Core Features
- **Reference-based caching** - Large values stored by reference, returning previews to agents
- **`@cache.cached()` decorator** - Simple, Pythonic API for caching tool results
- **Namespace isolation** - Separate caches for `public`, `session:<id>`, `user:<id>`, custom scopes
- **Access control** - Fine-grained permissions (READ, WRITE, UPDATE, DELETE, EXECUTE)
- **Private computation** - EXECUTE permission enables blind computation without data exposure
- **Preview strategies** - Truncate, sample, or paginate large values
- **Cross-tool data flow** - References act as a "data bus" between MCP tools

#### Backends
- **MemoryBackend** - In-memory caching for testing and simple use cases
- **SQLiteBackend** - Persistent caching with zero external dependencies
  - WAL mode for concurrent access
  - Thread-safe with connection-per-thread model
  - Cross-process reference sharing (multiple MCP servers on same machine)
  - XDG-compliant default path (`~/.cache/mcp-refcache/cache.db`)
  - Environment variable override (`MCP_REFCACHE_DB_PATH`)
- **RedisBackend** - Distributed caching for multi-user/multi-machine scenarios
  - Valkey/Redis compatible
  - Native TTL support via Redis expiration
  - Connection pooling for thread safety
  - Cross-tool reference sharing verified end-to-end
  - Docker deployment example with Valkey

#### FastMCP Integration
- `@cache.cached()` decorator for automatic caching of tool results
- `cache.resolve()` for cross-tool reference resolution
- `cache.get()` for preview retrieval with pagination
- Admin tools for cache management (optional)
- Cache documentation helpers for tool descriptions

#### Examples
- `examples/mcp_server.py` - Scientific calculator with sequences and matrices
- `examples/langfuse_integration.py` - Calculator with Langfuse tracing + SQLite backend
- `examples/data_tools.py` - Data analysis tools demonstrating cross-tool references
- `examples/redis-docker/` - Docker Compose setup with Valkey + 2 MCP servers

#### Testing & CI
- 691+ tests with 80%+ code coverage
- Parametrized backend tests (Memory, SQLite, Redis)
- GitHub Actions CI for Python 3.10-3.13
- Security scanning with Trivy
- Automated release workflow

### Documentation
- Comprehensive README with installation and usage examples
- CONTRIBUTING.md with development guidelines
- Inline docstrings with examples for all public APIs
- Docker deployment documentation for Redis backend

## [0.0.1] - Initial Development

### Added
- Initial project scaffold
- Core reference-based caching system
- Memory backend with basic operations
- Preview generation (truncate, sample, paginate)
- Pydantic models for type safety
- Basic test suite

<!-- Uncomment when repository is public
[Unreleased]: https://github.com/l4b4r4b4b4/mcp-refcache/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/l4b4r4b4b4/mcp-refcache/releases/tag/v0.1.0
[0.0.1]: https://github.com/l4b4r4b4b4/mcp-refcache/releases/tag/v0.0.1
-->
