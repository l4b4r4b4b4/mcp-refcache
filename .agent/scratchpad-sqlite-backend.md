# SQLite Backend Implementation

## Status: ✅ COMPLETE

## Overview

Implement a SQLite-based cache backend for mcp-refcache that enables:
1. **Persistence** - Cache survives process restarts
2. **Cross-tool references** - Multiple MCP servers on the same machine can share cached values
3. **Zero external dependencies** - SQLite is in Python stdlib

## Use Cases

### Primary: Cross-Tool Reference Sharing
```
MCP Server A (langfuse-calculator)     MCP Server B (finquant-mcp)
         |                                      |
         +-----------> SQLite DB <--------------+
                  (~/.cache/mcp-refcache/)

1. generate_primes(count=100) in Server A → returns ref_id: "calculator:abc123"
2. User passes ref_id to a tool in Server B
3. Server B resolves the reference from shared SQLite DB
```

### Secondary: Persistent Cache
- Cache persists across IDE restarts
- Long-running sessions can accumulate large datasets
- Resume work without regenerating expensive computations

## Design Decisions

### Database Location
- Default: `~/.cache/mcp-refcache/cache.db` (XDG-compliant)
- Configurable via constructor parameter
- Environment variable override: `MCP_REFCACHE_DB_PATH`

### Concurrency Model
- **WAL mode** (Write-Ahead Logging) for concurrent readers + one writer
- **Connection per operation** (thread-safe) vs **connection pool**
- SQLite handles file locking automatically

### Serialization
- `CacheEntry.value` can be any JSON-serializable data
- Store as JSON blob in SQLite
- `AccessPolicy` stored as JSON blob

### Schema Design

```sql
CREATE TABLE IF NOT EXISTS cache_entries (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,           -- JSON-serialized value
    namespace TEXT NOT NULL,
    policy_json TEXT NOT NULL,          -- JSON-serialized AccessPolicy
    created_at REAL NOT NULL,           -- Unix timestamp
    expires_at REAL,                    -- Unix timestamp or NULL
    metadata_json TEXT NOT NULL,        -- JSON-serialized metadata dict

    -- Indexes for common queries
    CHECK (json_valid(value_json)),
    CHECK (json_valid(policy_json)),
    CHECK (json_valid(metadata_json))
);

CREATE INDEX IF NOT EXISTS idx_namespace ON cache_entries(namespace);
CREATE INDEX IF NOT EXISTS idx_expires_at ON cache_entries(expires_at);
```

### TTL/Expiration
- Check expiration on read (lazy cleanup like MemoryBackend)
- Optional: Background cleanup thread for expired entries
- `expires_at` index enables efficient cleanup queries

## Protocol Methods to Implement

From `CacheBackend` protocol:

| Method | SQLite Implementation |
|--------|----------------------|
| `get(key)` | `SELECT ... WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)` |
| `set(key, entry)` | `INSERT OR REPLACE INTO cache_entries ...` |
| `delete(key)` | `DELETE FROM cache_entries WHERE key = ?` |
| `exists(key)` | `SELECT 1 FROM cache_entries WHERE key = ? AND ...` |
| `clear(namespace)` | `DELETE FROM cache_entries WHERE namespace = ?` or `DELETE FROM cache_entries` |
| `keys(namespace)` | `SELECT key FROM cache_entries WHERE namespace = ?` |

## File Structure

```
src/mcp_refcache/backends/
├── __init__.py          # Add SQLiteBackend export
├── base.py              # CacheBackend protocol (unchanged)
├── memory.py            # MemoryBackend (unchanged)
└── sqlite.py            # NEW: SQLiteBackend implementation

tests/
└── test_backends.py     # Add SQLiteBackend tests (mirror MemoryBackend tests)
```

## Implementation Plan

### Phase 1: Core Implementation ✅ COMPLETE
- [x] Create `SQLiteBackend` class
- [x] Implement database initialization (create tables, set WAL mode)
- [x] Implement `set()` - serialize and store CacheEntry
- [x] Implement `get()` - retrieve and deserialize CacheEntry
- [x] Implement `delete()` - remove entry
- [x] Implement `exists()` - check existence with expiration
- [x] Implement `clear()` - clear by namespace or all
- [x] Implement `keys()` - list keys with filtering

### Phase 2: Testing ✅ COMPLETE
- [x] Port all MemoryBackend tests to work with SQLiteBackend (parametrized fixtures)
- [x] Add SQLite-specific tests (persistence, file handling)
- [x] Test concurrent access from multiple threads
- [x] Test concurrent access from multiple processes (cross-tool use case)

### Phase 3: Integration ✅ COMPLETE
- [x] Update `backends/__init__.py` to export SQLiteBackend
- [x] Update main `__init__.py` to export SQLiteBackend
- [x] `backend` parameter already exists in `RefCache.__init__()`
- [x] Add example showing cross-tool reference sharing (`data_tools.py`)
- [x] Update `langfuse_integration.py` to use SQLite backend
- [x] Update `.zed/settings.json` with data-tools server config

### Phase 4: Polish
- [ ] Connection pooling (if needed for performance)
- [ ] Background expired entry cleanup (optional)
- [ ] Database migration support for schema changes

## Key Implementation Details

### Thread Safety
```python
class SQLiteBackend:
    def __init__(self, database_path: Path | str | None = None):
        self._database_path = self._resolve_path(database_path)
        self._local = threading.local()  # Thread-local connections
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self._database_path,
                check_same_thread=False,
            )
            self._local.connection.execute("PRAGMA journal_mode=WAL")
        return self._local.connection
```

### Serialization
```python
def _serialize_entry(self, entry: CacheEntry) -> dict:
    """Convert CacheEntry to storable dict."""
    return {
        "value_json": json.dumps(entry.value),
        "namespace": entry.namespace,
        "policy_json": json.dumps(entry.policy.model_dump()),
        "created_at": entry.created_at,
        "expires_at": entry.expires_at,
        "metadata_json": json.dumps(entry.metadata),
    }

def _deserialize_entry(self, row: sqlite3.Row) -> CacheEntry:
    """Convert database row to CacheEntry."""
    return CacheEntry(
        value=json.loads(row["value_json"]),
        namespace=row["namespace"],
        policy=AccessPolicy(**json.loads(row["policy_json"])),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        metadata=json.loads(row["metadata_json"]),
    )
```

### Default Path Resolution
```python
def _resolve_path(self, path: Path | str | None) -> Path:
    """Resolve database path with sensible defaults."""
    if path is not None:
        return Path(path)

    # Check environment variable
    env_path = os.environ.get("MCP_REFCACHE_DB_PATH")
    if env_path:
        return Path(env_path)

    # XDG-compliant default
    cache_home = os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
    return Path(cache_home) / "mcp-refcache" / "cache.db"
```

## Test Strategy

### Reuse Existing Tests
Create a pytest fixture that parametrizes over backend types:

```python
@pytest.fixture(params=["memory", "sqlite"])
def backend(request, tmp_path):
    if request.param == "memory":
        return MemoryBackend()
    elif request.param == "sqlite":
        return SQLiteBackend(tmp_path / "test.db")
```

This ensures both backends pass the same tests.

### SQLite-Specific Tests
- Persistence: Write, close, reopen, read
- File creation: Directory auto-creation
- Concurrent writes from multiple threads
- Concurrent access from multiple processes

## Dependencies

None - SQLite is in Python stdlib (`sqlite3` module).

## Questions to Resolve

1. **Connection pooling vs connection-per-thread?**
   - Thread-local connections are simpler and sufficient for most use cases
   - Can add pooling later if needed

2. **Background cleanup of expired entries?**
   - Start with lazy cleanup (on read) like MemoryBackend
   - Add optional background cleanup if performance becomes an issue

3. **Database migration strategy?**
   - For now, keep schema simple and backwards-compatible
   - Add version table later if needed

## Session Log

### Session 1
- Created scratchpad with design decisions
- Implemented `SQLiteBackend` class with all protocol methods
- Fixed `AccessPolicy` serialization (use `mode='json'` for Permission enums)
- Created parametrized test fixtures for both Memory and SQLite backends
- Added SQLite-specific tests (persistence, environment variables, concurrent access)
- All 649 tests pass (90 backend tests, 63 new for SQLite)
- Exported `SQLiteBackend` from `backends/__init__.py` and main `__init__.py`

### Session 2 (Current)
- Created `examples/data_tools.py` - second MCP server for cross-tool reference testing
- Updated `examples/langfuse_integration.py` to use SQLite backend
- Both servers now share `~/.cache/mcp-refcache/cache.db`
- Updated `.zed/settings.json` with data-tools server configuration
- Added tools: analyze_data, transform_data, aggregate_data, create_sample_data
- Added `list_shared_cache` tool to view all refs across tools
- Added `create_policy_example` tool for access policy testing

## Test Results

- 649 passed, 3 skipped
- Backend tests: 90 total (parametrized across memory, sqlite_memory, sqlite_file)
- New SQLite-specific tests: persistence, environment variables, concurrent processes

## Cross-Tool Usage Example

1. In Zed, restart IDE to load both MCP servers
2. In langfuse-calculator: `generate_primes(count=50)` → returns ref_id
3. In data-tools: `analyze_data(data="langfuse-calculator:abc123")` → statistics
4. Use `list_shared_cache()` to see all references from both servers

## References

- `src/mcp_refcache/backends/base.py` - CacheBackend protocol
- `src/mcp_refcache/backends/memory.py` - Reference implementation
- `tests/test_backends.py` - Test patterns to follow
