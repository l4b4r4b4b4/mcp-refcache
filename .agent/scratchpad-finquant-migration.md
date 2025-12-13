# Scratchpad: FinQuant-MCP Migration to @cache.cached() Pattern

## Task Overview

Migrate finquant-mcp from the old intrusive caching pattern (manual `cache.set()`/`cache.resolve()`)
to the new `@cache.cached()` decorator pattern that provides:

1. **Automatic caching** of tool outputs with structured responses
2. **Auto ref_id resolution** in inputs (agent can pass ref_ids from previous calls)
3. **Size-based responses** (full value for small results, preview + pagination for large)
4. **Langfuse tracing integration** (optional, for observability)

---

## Current Status: Information Gathering

### TODO 📋
- [ ] Document current finquant-mcp architecture
- [ ] Document new @cache.cached() decorator API
- [ ] Identify all tools that need migration
- [ ] Identify tools that return large data (need caching most)
- [ ] Design migration approach
- [ ] Create implementation plan
- [ ] Test plan

---

---

## Scope Boundaries: What mcp-refcache Is and Isn't

### What mcp-refcache IS FOR ✅

| Use Case | Example | TTL |
|----------|---------|-----|
| **Context explosion prevention** | Large API responses → preview + ref_id | Session |
| **Cross-tool data flow** | Tool A output → Tool B input via ref_id | Session |
| **Computed results caching** | get_returns(), correlation matrices | Hours |
| **Deterministic tool caching** | Same inputs → same output, cache forever | ∞ Infinite |
| **Expensive computation results** | Monte Carlo, optimization | Hours |
| **Session state** | User preferences, conversation context | Session |

### What mcp-refcache is NOT FOR ❌

| Use Case | Why Not | Better Alternative |
|----------|---------|-------------------|
| **Historical time series storage** | Specialized queries, massive scale | TimescaleDB, Parquet, InfluxDB |
| **User account database** | ACID transactions, relations | PostgreSQL, SQLite |
| **Document storage** | Full-text search, versioning | Elasticsearch, S3 |
| **Primary source of truth** | Needs durability guarantees | Proper database |

### The Key Distinction

```
Source Data (App's responsibility)     Computed Results (RefCache's job)
─────────────────────────────────     ────────────────────────────────
Yahoo Finance prices                → get_returns() output
CoinGecko historical data           → correlation matrix
User portfolio definitions          → Monte Carlo simulation results
                                    → Efficient frontier points
```

**RefCache caches the *results*, not the *source data*.**

### Deterministic Tool Caching (IMPORTANT)

For tools with **deterministic outputs** (same inputs → same result forever):

```python
@cache.cached(
    namespace="deterministic",
    ttl=None,  # ∞ Infinite - never expires
)
def calculate_correlation(prices: list[float]) -> float:
    # Pure function - same prices always give same correlation
    return np.corrcoef(prices)[0, 1]
```

**Use cases for infinite TTL:**
- Mathematical computations (correlation, covariance, returns)
- Data transformations (DataFrame → dict serialization)
- Derived metrics from immutable source data

**NOT for infinite TTL:**
- Anything that calls external APIs (might return different data)
- Anything with randomness (Monte Carlo)
- Anything time-dependent (current prices)

---

## Information Gathered

### 1. FinQuant-MCP Current Architecture

**Location:** `examples/finquant-mcp/`

**Dependencies (pyproject.toml):**
- fastmcp>=2.13.3
- mcp-refcache (git source)
- finquant (git source)
- numpy, pydantic, yfinance

**File Structure:**
```
src/finquant_mcp/
├── __init__.py
├── server.py           # FastMCP server + tool registration
├── storage.py          # PortfolioStore - manual RefCache usage
├── models.py           # Pydantic models
├── data_sources.py     # Yahoo Finance + CoinGecko APIs
└── tools/
    ├── portfolio.py    # Portfolio CRUD (6 tools)
    ├── analysis.py     # Analysis/metrics (7 tools)
    ├── optimization.py # EF + Monte Carlo (4 tools)
    └── data.py         # Data generation (7 tools)
```

**Current Caching Pattern (OLD - Intrusive):**
```python
# In server.py
cache = RefCache(
    name="finquant",
    default_ttl=3600,
    preview_config=PreviewConfig(
        size_mode=SizeMode.CHARACTER,
        max_size=500,
        default_strategy=PreviewStrategy.SAMPLE,
    ),
)

# In storage.py - Manual cache usage
class PortfolioStore:
    def store(self, portfolio, name):
        ref = self.cache.set(key=name, value=serialized, ...)
        return ref.ref_id

    def get(self, name):
        return self.cache.resolve(ref_id)
```

**Current Tool Pattern (NO decorator):**
```python
# In tools/analysis.py
@mcp.tool
def get_portfolio_metrics(name: str) -> dict[str, Any]:
    data = store.get(name)  # Manual resolve
    # ... compute ...
    return {...}  # Raw dict - NO caching, NO ref_id
```

### 2. New @cache.cached() Decorator API

**Location:** `src/mcp_refcache/cache.py` (lines 438-600+)

**Signature:**
```python
@cache.cached(
    namespace: str = "public",
    policy: AccessPolicy | None = None,
    ttl: float | None = None,
    max_size: int | None = None,
    resolve_refs: bool = True,
    actor: str = "agent",
    # Context-scoped parameters
    namespace_template: str | None = None,
    owner_template: str | None = None,
    session_scoped: bool = False,
)
```

**Key Features:**
1. **Pre-execution**: Recursively resolves ref_ids in ALL inputs
2. **Post-execution**: Always returns structured response dict
3. **Size-based decision**: Full value OR preview based on max_size

**Response Format (Small Result):**
```python
{
    "ref_id": "finquant:abc123",
    "value": {...},  # Full data
    "is_complete": True,
    "size": 150,
    "total_items": 5,
}
```

**Response Format (Large Result):**
```python
{
    "ref_id": "finquant:abc123",
    "preview": [...],  # Sample/truncated
    "is_complete": False,
    "preview_strategy": "sample",
    "total_items": 1000,
    "original_size": 5000,
    "preview_size": 100,
    "page": 1,
    "total_pages": 20,
    "message": "Use get_cached_result(ref_id='finquant:abc123') to paginate.",
}
```

**Correct Decorator Order:**
```python
@mcp.tool
@cache.cached(namespace="data")
def my_tool(input: str) -> dict:
    return {"data": ...}
```

### 3. FinQuant-MCP Tool Inventory

**Portfolio Management (6 tools) - tools/portfolio.py:**
| Tool | Returns | Needs Caching? |
|------|---------|----------------|
| create_portfolio | summary dict | ⚠️ Medium (stores via PortfolioStore) |
| get_portfolio | portfolio dict | ✅ Yes (can be large) |
| list_portfolios | list of summaries | ⚠️ Medium |
| delete_portfolio | status dict | ❌ No (mutation) |
| update_portfolio_weights | status dict | ❌ No (mutation) |
| clone_portfolio | summary dict | ⚠️ Medium |

**Analysis Tools (7 tools) - tools/analysis.py:**
| Tool | Returns | Needs Caching? |
|------|---------|----------------|
| get_portfolio_metrics | metrics dict | ⚠️ Medium |
| get_returns | dates + returns arrays | ✅ YES (large - 252 days × N stocks) |
| get_correlation_matrix | N×N matrix | ✅ YES (can be large) |
| get_covariance_matrix | N×N matrix | ✅ YES (can be large) |
| compare_portfolios | comparison dict | ⚠️ Medium |
| get_individual_stock_metrics | per-stock metrics | ⚠️ Medium |
| get_drawdown_analysis | drawdown series | ✅ YES (252+ data points) |

**Optimization Tools (4 tools) - tools/optimization.py:**
| Tool | Returns | Needs Caching? |
|------|---------|----------------|
| optimize_portfolio | optimal weights | ⚠️ Medium |
| run_monte_carlo | simulation results | ✅ YES (5000+ trials) |
| get_efficient_frontier | frontier points | ✅ YES (50+ points) |
| apply_optimization | status dict | ❌ No (mutation) |

**Data Tools (7 tools) - tools/data.py:**
| Tool | Returns | Needs Caching? |
|------|---------|----------------|
| generate_price_series | price DataFrame | ✅ YES (252+ days × N stocks) |
| generate_portfolio_scenarios | multiple scenarios | ✅ YES (very large) |
| get_sample_portfolio_data | sample data | ⚠️ Medium |
| get_trending_coins | trending list | ⚠️ Medium (API response) |
| search_crypto_coins | search results | ⚠️ Medium (API response) |
| get_crypto_info | coin details | ⚠️ Medium |
| list_crypto_symbols | symbol list | ❌ No (static) |

**Priority for Caching (Large Data):**
1. `get_returns` - 252 days × N stocks (can be 2500+ data points)
2. `generate_price_series` - 252+ days × N stocks
3. `run_monte_carlo` - 5000+ simulation trials
4. `get_efficient_frontier` - 50+ frontier points
5. `generate_portfolio_scenarios` - multiple complete scenarios
6. `get_correlation_matrix` / `get_covariance_matrix` - N×N matrices
7. `get_drawdown_analysis` - 252+ data points

### 4. Current mcp-refcache Imports in FinQuant

**server.py imports:**
```python
from mcp_refcache import (
    CacheResponse,
    PreviewConfig,
    PreviewStrategy,
    RefCache,
    SizeMode,
)
from mcp_refcache.fastmcp import (
    cache_instructions,
)
```

**storage.py imports:**
```python
from mcp_refcache import AccessPolicy, Permission
from mcp_refcache import RefCache  # TYPE_CHECKING only
```

### 5. Example of New Pattern (from mcp_server.py)

**Scientific Calculator Example:**
```python
# Initialize cache
cache = RefCache(
    name="calculator",
    default_ttl=3600,
    preview_config=PreviewConfig(
        max_size=64,  # tokens
        default_strategy=PreviewStrategy.SAMPLE,
    ),
)

# Tool with new decorator
@mcp.tool
@cache.cached(namespace="sequences")
async def generate_sequence(input: SequenceInput) -> list[int]:
    """Generate a sequence - decorator handles caching."""
    # Just return raw data - decorator wraps it
    return sequence  # list[int]

# Decorator changes return to dict[str, Any] with ref_id, value/preview, etc.
```

### 6. PortfolioStore Consideration

The `PortfolioStore` class provides:
1. **Serialization** - Converting FinQuant Portfolio objects to JSON
2. **Name → ref_id mapping** - Tracking portfolio names
3. **CRUD operations** - store, get, delete, exists, list

**Options:**
- **Option A**: Keep PortfolioStore, add `@cache.cached()` to tools that return data
- **Option B**: Refactor PortfolioStore to use new patterns
- **Option C**: Migrate completely - store portfolios with `@cache.cached()` on create

**Recommendation:** Option A - incremental migration
- Keep PortfolioStore for portfolio persistence (it works)
- Add `@cache.cached()` to analysis/data tools that return large results
- This validates the decorator without breaking existing functionality

### 7. Langfuse Integration (Optional Enhancement)

The calculator example has `TracedRefCache` pattern in `examples/langfuse_integration.py`:

```python
from examples.langfuse_integration import TracedRefCache

base_cache = RefCache(...)
cache = TracedRefCache(base_cache)  # Wraps with Langfuse spans
```

**For finquant-mcp:** Can add later as Phase 2 enhancement.

---

## Security Model for Portfolio Data

### The Problem

Portfolio data is **sensitive financial information**:
- Individual allocations reveal investment strategy
- Holdings data could be proprietary
- Analysis results (returns, metrics) are derived from private data
- Different users should NOT see each other's portfolios

### Access Control Levels

**Level 1: Namespace Isolation (Who owns the cache entry)**
```python
# User-scoped namespace - each user's data is isolated
namespace_template = "user:{user_id}"
# Result: "user:alice", "user:bob", etc.

# Or with organization:
namespace_template = "org:{org_id}:user:{user_id}"
# Result: "org:acme:user:alice"
```

**Level 2: Ownership (Who can do what)**
```python
owner_template = "user:{user_id}"
# Result: owner="user:alice" - Alice gets owner_permissions

policy = AccessPolicy(
    user_permissions=Permission.READ,  # Other users: READ only
    owner_permissions=Permission.FULL,  # Owner: full access
    agent_permissions=Permission.READ | Permission.EXECUTE,  # Agents: read + compute
)
```

**Level 3: Session Binding (Temporary access)**
```python
session_scoped = True
# Result: bound_session="sess-123" - only this session can access
```

### Recommended Patterns for FinQuant

**Pattern A: User-Owned Portfolio Data (Default)**
```python
@mcp.tool
@cache.cached(
    namespace_template="user:{user_id}:portfolios",
    owner_template="user:{user_id}",
    policy=AccessPolicy(
        user_permissions=Permission.READ,  # Other users can't read
        owner_permissions=Permission.FULL,  # Owner has full access
        agent_permissions=Permission.READ | Permission.EXECUTE,  # Agents can read/use
    ),
)
def get_returns(name: str) -> dict:
    ...
```

**Pattern B: Session-Scoped Analysis (More Restrictive)**
```python
@mcp.tool
@cache.cached(
    namespace_template="user:{user_id}:analysis",
    owner_template="user:{user_id}",
    session_scoped=True,  # Only this session can access
)
def run_monte_carlo(name: str, num_trials: int) -> dict:
    # Expensive computation - cached per user, per session
    ...
```

**Pattern C: Public Reference Data**
```python
@mcp.tool
@cache.cached(
    namespace="market_data",  # Static namespace - shared by all
    policy=AccessPolicy(
        user_permissions=Permission.FULL,
        agent_permissions=Permission.FULL,  # Everyone can access
    ),
)
def get_trending_coins() -> list:
    # Public market data - OK to share
    ...
```

### What We Get

| Data Type | Pattern | Namespace | Owner | Session Bound |
|-----------|---------|-----------|-------|---------------|
| Portfolio returns | A | `user:{id}:portfolios` | `user:{id}` | No |
| Monte Carlo results | B | `user:{id}:analysis` | `user:{id}` | Yes |
| Correlation matrices | A | `user:{id}:portfolios` | `user:{id}` | No |
| Trending coins | C | `market_data` | None | No |
| Price series (synthetic) | A | `user:{id}:data` | `user:{id}` | No |

### Agent Behavior

With `agent_permissions=Permission.READ | Permission.EXECUTE`:
- ✅ Agent can **read** portfolio data (to display to user)
- ✅ Agent can **pass ref_id** to other tools (cross-tool workflow)
- ✅ Agent can **use in computation** (EXECUTE)
- ❌ Agent cannot **write/update/delete** user's data

For more restrictive:
```python
agent_permissions=Permission.EXECUTE  # Can use, cannot see
```

### Implementation Approach

**Phase 1 (MVP):** Use Pattern A for all user data
- Simple: Just add namespace_template and owner_template
- Safe: User data isolated by user_id
- Agent-friendly: Agents can still read to display

**Phase 2 (Enhancement):** Add session scoping for expensive computations
- Monte Carlo, Efficient Frontier → session-scoped (recomputed per session)
- Portfolio metrics → user-scoped (persistent across sessions)

**Phase 3 (Multi-tenant):** Add org_id for enterprise
- `org:{org_id}:user:{user_id}:portfolios`
- Organization admins can see all users' data

### PortfolioStore Security Note

The current `PortfolioStore.store()` uses:
```python
policy = AccessPolicy(
    user_permissions=Permission.FULL,
    agent_permissions=Permission.FULL,  # ⚠️ Too permissive!
)
```

**Future improvement (Phase 2):**
- Change to `agent_permissions=Permission.READ | Permission.EXECUTE`
- Add user_id to namespace via context
- Consider: Should PortfolioStore also use context-scoped caching?

**For now:** Keep PortfolioStore as-is, focus on `@cache.cached()` migration first.

---

## Design Decisions

### 1. Migration Strategy: Incremental (Option A)

**Rationale:**
- Keep PortfolioStore working (proven, tested)
- Add `@cache.cached()` to high-priority tools first
- Validate decorator works in real-world MCP server
- Lower risk, easier to debug

### 2. Security by Default

**All user portfolio data uses:**
```python
namespace_template="user:{user_id}:portfolios"
owner_template="user:{user_id}"
```

**Public market data uses:**
```python
namespace="market_data"
# No owner, no user scoping
```

### 3. Tools to Migrate (Phase 1 - High Priority)

1. `get_returns` - Large time series data
2. `generate_price_series` - Large synthetic data
3. `run_monte_carlo` - Very large simulation results
4. `get_efficient_frontier` - Frontier visualization data
5. `get_correlation_matrix` - Matrix data
6. `get_covariance_matrix` - Matrix data

### 4. Namespace Strategy (Updated with Security)

| Namespace Template | Tools | Security |
|--------------------|-------|----------|
| `user:{user_id}:analysis` | get_returns, correlation, covariance, drawdown | User-owned |
| `user:{user_id}:optimization` | run_monte_carlo, get_efficient_frontier | User-owned |
| `user:{user_id}:data` | generate_price_series, generate_portfolio_scenarios | User-owned |
| `user:{user_id}:portfolios` | (keep existing - PortfolioStore) | User-owned |
| `market_data` | get_trending_coins, search_crypto_coins | Public |

### 5. Cache Configuration

```python
cache = RefCache(
    name="finquant",
    default_ttl=3600,  # 1 hour
    preview_config=PreviewConfig(
        size_mode=SizeMode.TOKEN,  # Use tokens, not characters
        max_size=200,  # ~200 tokens before preview
        default_strategy=PreviewStrategy.SAMPLE,
    ),
)
```

---

## Implementation Plan

### Phase 1: Core Migration (High-Priority Tools + Security)

**Step 1: Update server.py**
- Change SizeMode to TOKEN (better for LLM context)
- Increase max_size to ~200 tokens (financial data is dense)
- Ensure cache is passed to all tool registration functions

**Step 2: Update tools/analysis.py**
- Add cache parameter to `register_analysis_tools(mcp, store, cache)`
- Add `@cache.cached()` with user-scoped namespace to:
  - `get_returns`
  - `get_correlation_matrix`
  - `get_covariance_matrix`
  - `get_drawdown_analysis`

Example pattern:
```python
@mcp.tool
@cache.cached(
    namespace_template="user:{user_id}:analysis",
    owner_template="user:{user_id}",
)
def get_returns(name: str, return_type: str = "daily") -> dict[str, Any]:
    ...
```

**Step 3: Update tools/optimization.py**
- Add cache parameter to `register_optimization_tools(mcp, store, cache)`
- Add `@cache.cached()` with user-scoped namespace to:
  - `run_monte_carlo`
  - `get_efficient_frontier`

**Step 4: Update tools/data.py**
- Add `@cache.cached()` with user-scoped namespace to:
  - `generate_price_series`
  - `generate_portfolio_scenarios`
- Add public namespace for market data tools:
  - `get_trending_coins`
  - `search_crypto_coins`

**Step 5: Test**
- Run existing tests (should still pass)
- Add integration tests for new caching behavior
- Test namespace isolation (different user_ids get different caches)
- Live test in Zed with Claude

### Phase 2: Langfuse Tracing (Optional)

- Wrap cache with TracedRefCache
- Verify traces appear in Langfuse dashboard

### Phase 3: Valkey Backend (Cross-Server)

- After migration validated, add Valkey backend
- Enable Calculator + FinQuant to share cache

---

## Files to Modify

### Primary Changes
| File | Changes |
|------|---------|
| `server.py` | Update PreviewConfig, maybe switch to TOKEN mode |
| `tools/analysis.py` | Add @cache.cached() to 4 tools |
| `tools/optimization.py` | Add @cache.cached() to 2 tools, add cache param |
| `tools/data.py` | Add @cache.cached() to 2 tools |

### Signature Changes Needed
| File | Current | New |
|------|---------|-----|
| `tools/optimization.py` | `register_optimization_tools(mcp, store)` | `register_optimization_tools(mcp, store, cache)` |

---

## Test Plan

### Unit Tests
- Verify existing tests still pass
- Add tests for cached tool responses (ref_id presence)

### Integration Tests
1. **Small result test**: Call tool with small data → verify `is_complete: true`
2. **Large result test**: Call tool with large data → verify preview + pagination
3. **Ref resolution test**: Pass ref_id from one tool to another
4. **Cache hit test**: Same inputs → same ref_id

### Live Testing (Zed + Claude)
1. Create portfolio from Yahoo Finance
2. Call `get_returns` → should get ref_id + preview
3. Call `get_cached_result(ref_id, page=2)` → should paginate
4. Call `run_monte_carlo` → should get ref_id + preview (5000 trials)
5. Verify agent can work with previews without context explosion

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Run tests after each change |
| Tool return type changes | Decorator handles annotation update |
| PortfolioStore conflicts | Keep PortfolioStore unchanged in Phase 1 |
| Performance regression | Cache is in-memory, should be fast |

---

## Questions Resolved

1. **Should we migrate PortfolioStore?**
   - No, keep it for now. It handles Portfolio object serialization.

2. **Which tools need caching most?**
   - Analysis tools returning time series (get_returns, drawdowns)
   - Optimization tools (Monte Carlo, Efficient Frontier)
   - Data generation tools (price series, scenarios)

3. **Token vs Character sizing?**
   - Token (better for LLM context management)

---

## Next Session Starting Prompt

```
FinQuant-MCP Migration to @cache.cached() Pattern

## Context
- mcp-refcache v0.0.1 ready (586 tests)
- finquant-mcp uses OLD manual cache pattern (cache.set/resolve)
- Need to migrate to new @cache.cached() decorator
- See `.agent/scratchpad-finquant-migration.md` for full context

## What Was Researched
- Documented all 24 finquant-mcp tools
- Identified 8 high-priority tools for caching (large data)
- Designed incremental migration (keep PortfolioStore for now)
- Designed security model with user-scoped namespaces

## Security Model (IMPORTANT)
Portfolio data is sensitive - use context-scoped caching:

```python
# User-owned data (analysis, optimization, portfolios)
@cache.cached(
    namespace_template="user:{user_id}:analysis",
    owner_template="user:{user_id}",
)

# Public data (market data, trending coins)
@cache.cached(namespace="market_data")
```

## Implementation Plan (Phase 1)
1. Update `server.py`: Switch to TOKEN mode, max_size=200
2. Update `tools/analysis.py`:
   - Add cache param to register_analysis_tools
   - Add @cache.cached() with user-scoped namespace to 4 tools
3. Update `tools/optimization.py`:
   - Add cache param to register_optimization_tools
   - Add @cache.cached() with user-scoped namespace to 2 tools
4. Update `tools/data.py`:
   - Add @cache.cached() to data generation tools (user-scoped)
   - Add @cache.cached() to market data tools (public namespace)
5. Run tests, live test in Zed

## Files to Modify
- examples/finquant-mcp/src/finquant_mcp/server.py
- examples/finquant-mcp/src/finquant_mcp/tools/analysis.py
- examples/finquant-mcp/src/finquant_mcp/tools/optimization.py
- examples/finquant-mcp/src/finquant_mcp/tools/data.py

## Current Test Error to Fix First
```
TypeError: register_analysis_tools() takes 2 positional arguments but 3 were given
```
server.py already passes cache, but tools/analysis.py doesn't accept it yet.

## Guidelines
- Follow `.rules` (TDD, document as you go)
- Run tests after each file change
- Use context-scoped caching for user data security
- Keep PortfolioStore unchanged (works fine)

## First Task
Start with `tools/analysis.py`:
1. Add cache parameter: `register_analysis_tools(mcp, store, cache)`
2. Add @cache.cached() to get_returns with user-scoped namespace
3. Run tests to verify no breakage
4. Test that tool returns structured response with ref_id
```

---

## Session Log

### Session 1: Information Gathering (Current)
- Created scratchpad
- Documented finquant-mcp architecture
- Documented new @cache.cached() API
- Inventoried all 24 tools
- Identified 8 high-priority tools for migration
- Designed security model with user-scoped namespaces
- Created implementation plan with security by default
- Created test plan
- Documented PortfolioStore security concern for Phase 2
- Ready for implementation in next session

---

## Key Insights

1. **Portfolio data is sensitive** - must use context-scoped caching with user isolation
2. **Agent permissions matter** - READ|EXECUTE allows display and computation, not modification
3. **Public vs Private data** - market data (trending coins) can be public, user portfolios must be private
4. **Incremental migration** - keep PortfolioStore working, add decorator to analysis/data tools
5. **Test error exists** - server.py already passes cache, but analysis.py doesn't accept it yet
6. **Deterministic vs Non-deterministic** - pure computations can use infinite TTL, API calls cannot
7. **Scope boundaries** - RefCache is for tool outputs/results, NOT for source data storage

---

## TTL Strategy by Tool

| Tool | Deterministic? | TTL | Rationale |
|------|----------------|-----|-----------|
| `get_returns` | ✅ Yes (from stored prices) | ∞ or 24h | Same prices → same returns |
| `get_correlation_matrix` | ✅ Yes | ∞ or 24h | Pure math |
| `get_covariance_matrix` | ✅ Yes | ∞ or 24h | Pure math |
| `get_drawdown_analysis` | ✅ Yes | ∞ or 24h | Pure math |
| `run_monte_carlo` | ❌ No (random) | 1h | Different each run |
| `get_efficient_frontier` | ✅ Yes | ∞ or 24h | Optimization is deterministic |
| `generate_price_series` | ⚠️ Depends on seed | 1h or ∞ | With seed=deterministic |
| `get_trending_coins` | ❌ No (API) | 15min | Changes frequently |

**Note:** "∞ or 24h" means infinite for pure computations, but 24h is safer in case source data gets updated.

---

## Files Reference

| File | Purpose | Changes Needed |
|------|---------|----------------|
| `server.py` | FastMCP server init | Already passes cache (fix test error by updating tools) |
| `tools/analysis.py` | 7 analysis tools | Add cache param + @cache.cached() to 4 tools |
| `tools/optimization.py` | 4 optimization tools | Add cache param + @cache.cached() to 2 tools |
| `tools/data.py` | 7 data tools | Add @cache.cached() to 4 tools (2 user, 2 public) |
| `storage.py` | PortfolioStore | Phase 2: Update security policy |

---

## Validation Checklist (End of Migration)

- [ ] All tests pass (149 tests)
- [ ] `get_returns` returns `{ref_id, value/preview, is_complete, ...}`
- [ ] Large results (252 days × N stocks) get preview, not full data
- [ ] Different user_ids get different cache namespaces
- [ ] Agents can read portfolio data (for display)
- [ ] Agents cannot write/update/delete portfolio data
- [ ] Trending coins uses public namespace (shared)
- [ ] Live test in Zed works with Yahoo Finance data
- [ ] Deterministic tools use appropriate TTL (long/infinite)
- [ ] Non-deterministic tools use short TTL
