# SQLite Backend Implementation

## Status: 🚧 IN PROGRESS

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

### Phase 1: Core Implementation
- [ ] Create `SQLiteBackend` class
- [ ] Implement database initialization (create tables, set WAL mode)
- [ ] Implement `set()` - serialize and store CacheEntry
- [ ] Implement `get()` - retrieve and deserialize CacheEntry
- [ ] Implement `delete()` - remove entry
- [ ] Implement `exists()` - check existence with expiration
- [ ] Implement `clear()` - clear by namespace or all
- [ ] Implement `keys()` - list keys with filtering

### Phase 2: Testing
- [ ] Port all MemoryBackend tests to work with SQLiteBackend
- [ ] Add SQLite-specific tests (persistence, file handling)
- [ ] Test concurrent access from multiple threads
- [ ] Test concurrent access from multiple processes (cross-tool use case)

### Phase 3: Integration
- [ ] Update `backends/__init__.py` to export SQLiteBackend
- [ ] Add `backend` parameter to `RefCache.__init__()`
- [ ] Add example showing cross-tool reference sharing
- [ ] Update documentation

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

### Session 1 (Current)
- Created scratchpad with design decisions
- Ready to begin implementation

## References

- `src/mcp_refcache/backends/base.py` - CacheBackend protocol
- `src/mcp_refcache/backends/memory.py` - Reference implementation
- `tests/test_backends.py` - Test patterns to follow
