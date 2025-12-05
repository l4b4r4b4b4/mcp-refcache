# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffold
- Core reference-based caching system (from BundesMCP)
- Memory backend with disk persistence
- Preview generation (truncate, sample, paginate)
- Return type options (ValueReturnType, ReferenceReturnType)
- Redis backend (optional dependency)
- FastMCP integration tools (optional dependency)

### Planned for v0.0.1
- Namespace hierarchy (public, session, user, custom)
- Permission model (READ, WRITE, UPDATE, DELETE, EXECUTE)
- Separate user/agent access control
- TTL per namespace
- Reference metadata (tags, descriptions)
- Private computation support via EXECUTE permission

## [0.0.1] - Unreleased

### Added
- Namespace support: `public`, `session:<id>`, `user:<id>`, `custom:<name>`
- Permission flags: `READ`, `WRITE`, `UPDATE`, `DELETE`, `EXECUTE`
- `AccessPolicy` for separate user and agent permissions
- `EXECUTE` permission for blind/private computation
- TTL configuration per namespace
- Reference metadata (tags, descriptions, schema types)
- Hierarchical namespace permission inheritance

### Changed
- Refactored imports for standalone library use
- Made Redis and FastMCP optional dependencies
- Cleaned up public API exports

### Fixed
- Removed BundesMCP-specific dependencies
- Made Redis URL configurable (no hardcoded settings)

[Unreleased]: https://github.com/l4b4r4b4b4/mcp-refcache/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/l4b4r4b4b4/mcp-refcache/releases/tag/v0.0.1