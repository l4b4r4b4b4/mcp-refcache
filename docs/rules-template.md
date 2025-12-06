# mcp-refcache Integration Rules for Coding Assistants

This file provides rules and patterns for AI coding assistants working on MCP servers that use the `mcp-refcache` library. Copy the relevant sections to your project's `.rules` file.

---

## Overview

`mcp-refcache` is a reference-based caching library for FastMCP servers. It enables:
- **Automatic structured responses**: All decorated tools return `ref_id + value/preview`
- **Deep ref_id resolution**: Any input can contain ref_ids that get auto-resolved
- **Size-based response switching**: Small results include full value, large results include preview
- **Pagination**: Agents can page through large cached data
- **Private computation**: Use values in computations without exposing them

---

## Hard Rules

### 1. Use `@cache.cached()` on All Tools That Return Data

The decorator automatically handles caching and structured responses:

```python
@mcp.tool
@cache.cached(namespace="data")
def generate_data(size: int) -> list[int]:
    """Generate a list of integers."""
    return list(range(size))

# Small result returns:
# {"ref_id": "...", "value": [0, 1, 2], "is_complete": True, "size": 12, "total_items": 3}

# Large result returns:
# {"ref_id": "...", "preview": [0, 50, 100, ...], "is_complete": False, "preview_strategy": "sample", ...}
```

The tool body stays clean - no caching logic needed!

### 2. Always Register a `get_cached_result` Tool

Every MCP server using RefCache **MUST** expose a pagination tool:

```python
@mcp.tool
def get_cached_result(
    ref_id: str,
    page: int | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    """Retrieve a cached result, optionally with pagination.

    Args:
        ref_id: The reference ID returned by other tools.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dictionary with preview, pagination info, and total_items.
    """
    try:
        response = cache.get(
            ref_id,
            page=page,
            page_size=page_size,
            actor="agent",
        )
        
        result = {
            "ref_id": ref_id,
            "preview": response.preview,
            "preview_strategy": response.preview_strategy.value,
            "total_items": response.total_items,
        }
        
        if response.page is not None:
            result["page"] = response.page
            result["total_pages"] = response.total_pages
            
        return result
        
    except KeyError:
        return {"error": "Not found", "ref_id": ref_id}
```

### 3. Use Token-Based Size Limiting

Always use token-based sizing for accurate LLM context management:

```python
from mcp_refcache import (
    RefCache,
    PreviewConfig,
    PreviewStrategy,
    SizeMode,
    TiktokenAdapter,
)

cache = RefCache(
    name="my-server",
    default_ttl=3600,
    tokenizer=TiktokenAdapter("gpt-4o"),  # Use tiktoken!
    preview_config=PreviewConfig(
        size_mode=SizeMode.TOKEN,  # NOT CHARACTER
        max_size=500,  # tokens, not characters
        default_strategy=PreviewStrategy.SAMPLE,
    ),
)
```

### 4. Include Cache Instructions in Server

Use the `cache_instructions()` helper in your FastMCP server:

```python
from mcp_refcache.fastmcp import cache_instructions

mcp = FastMCP(
    name="MyServer",
    instructions=f"""Your server description here.

{cache_instructions()}
""",
)
```

---

## Key Feature: Automatic Ref_id Resolution

The `@cache.cached()` decorator automatically resolves ref_ids anywhere in inputs:

```python
@mcp.tool
@cache.cached(namespace="results")
def process_data(prices: dict[str, list[float]], multiplier: float) -> dict[str, Any]:
    """Process price data with a multiplier."""
    return {symbol: [p * multiplier for p in vals] for symbol, vals in prices.items()}
```

**Agent can call with ref_ids at ANY nesting level:**

```python
# All of these ref_ids get auto-resolved before the function runs:
process_data(
    prices={
        "AAPL": [100, 101, "myapp:abc111"],  # ref_id inside list
        "MSX": "myapp:abc122"                 # ref_id as dict value
    },
    multiplier="myapp:abc123"                 # ref_id as top-level param
)

# Function receives fully resolved values:
# prices={"AAPL": [100, 101, 102.5], "MSX": [200, 201, 202]}, multiplier=2.0
```

---

## Response Format

### Small Result (fits within max_size)

```python
{
    "ref_id": "myapp:abc123",
    "value": [1, 2, 3, 4, 5],  # Full data included
    "is_complete": True,
    "size": 15,  # tokens or characters
    "total_items": 5,
}
```

### Large Result (exceeds max_size)

```python
{
    "ref_id": "myapp:abc123",
    "preview": [1, 50, 100, "... and 997 more"],
    "is_complete": False,
    "preview_strategy": "sample",
    "total_items": 1000,
    "original_size": 5000,
    "preview_size": 100,
    "page": 1,
    "total_pages": 20,
    "message": "Use get_cached_result(ref_id='myapp:abc123') to paginate.",
}
```

---

## Soft Rules

### 1. Use Namespaces for Organization

Group related cached data by namespace:

```python
# Portfolio data
@cache.cached(namespace="portfolios")
def create_portfolio(...): ...

# Generated data
@cache.cached(namespace="data")
def generate_prices(...): ...

# Computation results
@cache.cached(namespace="results")
def run_optimization(...): ...
```

### 2. Override max_size Per Tool When Needed

```python
# Tool that returns very large data - use smaller preview
@cache.cached(namespace="data", max_size=200)
def get_huge_dataset(...): ...

# Tool that returns small, critical data - allow larger threshold
@cache.cached(namespace="config", max_size=2000)
def get_configuration(...): ...
```

### 3. Consider Preview Strategy by Data Type

Choose appropriate preview strategies in cache config:

```python
# Lists/sequences - use SAMPLE for representative items
PreviewStrategy.SAMPLE

# Text/strings - use TRUNCATE to show beginning
PreviewStrategy.TRUNCATE

# Tabular data - use PAGINATE for sequential access
PreviewStrategy.PAGINATE
```

---

## Common Patterns

### Pattern 1: Simple Cached Tool

```python
@mcp.tool
@cache.cached(namespace="data")
def generate_sequence(sequence_type: str, count: int = 100) -> list[int]:
    """Generate a mathematical sequence.
    
    Large results are cached and returned as ref_id + preview.
    Use get_cached_result(ref_id, page=N) to paginate.
    """
    if sequence_type == "fibonacci":
        return compute_fibonacci(count)
    elif sequence_type == "primes":
        return compute_primes(count)
    # ...
```

### Pattern 2: Tool Chain with References

```python
# Step 1: Generate data (returns structured response with ref_id)
@mcp.tool
@cache.cached(namespace="data")
def generate_prices(symbols: list[str], days: int) -> dict[str, Any]:
    """Generate price series data."""
    return {"symbols": symbols, "prices": compute_prices(symbols, days)}

# Step 2: Process data (accepts ref_id, auto-resolved before execution)
@mcp.tool
@cache.cached(namespace="results")
def compute_returns(prices: dict[str, Any]) -> dict[str, Any]:
    """Compute returns from price data.
    
    Args:
        prices: Price data dict OR a ref_id from generate_prices.
    """
    # prices is already resolved - decorator handled it!
    return calculate_returns(prices)
```

### Pattern 3: Private Computation

```python
# Store with EXECUTE-only for agents
@mcp.tool
def store_secret(name: str, value: float) -> dict[str, Any]:
    """Store a secret value that agents cannot read."""
    ref = cache.set(
        key=name,
        value=value,
        policy=AccessPolicy(
            user_permissions=Permission.FULL,
            agent_permissions=Permission.EXECUTE,  # Can use, can't see!
        ),
    )
    return {"ref_id": ref.ref_id, "message": "Stored securely"}

@mcp.tool
def compute_with_secret(secret_ref: str, expression: str) -> dict[str, Any]:
    """Use secret in computation without exposing it."""
    secret = cache.resolve(secret_ref, actor="agent")  # EXECUTE allows this
    result = evaluate_expression(expression, x=secret)
    return {"result": result}
```

### Pattern 4: Disable Ref Resolution When Not Needed

```python
# For tools that should receive raw string inputs, not resolved refs
@cache.cached(namespace="search", resolve_refs=False)
def search_by_id(query: str) -> list[dict]:
    """Search by ID string - don't resolve as ref_id."""
    return database.search(query)
```

---

## Anti-Patterns to Avoid

### ❌ Manual Caching in Tool Body

```python
# BAD - Clutters tool with caching logic
@mcp.tool
def get_data() -> dict[str, Any]:
    data = compute_data()
    ref = cache.set(key="data", value=data, namespace="data")
    response = cache.get(ref.ref_id)
    return {"ref_id": ref.ref_id, "preview": response.preview}

# GOOD - Use decorator
@mcp.tool
@cache.cached(namespace="data")
def get_data() -> list[Any]:
    return compute_data()
```

### ❌ Not Exposing Pagination Tool

```python
# BAD - No way for agents to paginate cached data
cache = RefCache(name="my-cache")
# ... tools use @cache.cached() but no get_cached_result registered
```

### ❌ Using Character-Based Sizing

```python
# BAD - Characters don't reflect actual token usage
preview_config=PreviewConfig(
    size_mode=SizeMode.CHARACTER,  # Inaccurate for LLMs!
    max_size=500,
)
```

### ❌ Expecting Raw Values from Decorated Functions

```python
# BAD - Decorated functions return structured responses
@cache.cached()
def get_value() -> int:
    return 42

result = get_value()  # result is {"ref_id": "...", "value": 42, ...}, NOT 42!
```

---

## Checklist for MCP Server Integration

- [ ] RefCache initialized with `TiktokenAdapter` tokenizer
- [ ] `PreviewConfig` uses `SizeMode.TOKEN`
- [ ] `cache_instructions()` included in server instructions
- [ ] `get_cached_result` tool registered
- [ ] Tools use `@cache.cached(namespace="...")` decorator
- [ ] Tool docstrings mention that inputs can accept ref_ids
- [ ] Tool docstrings mention that large results return ref_id + preview

---

## Example Server Structure

```
my-mcp-server/
├── src/my_server/
│   ├── __init__.py
│   ├── server.py          # FastMCP + RefCache setup, get_cached_result tool
│   ├── storage.py         # Domain-specific storage using cache
│   └── tools/
│       ├── __init__.py
│       ├── data.py        # Tools with @cache.cached() decorator
│       └── analysis.py    # Tools that accept ref_ids in inputs
├── pyproject.toml
└── .rules                  # Include this template!
```

---

## Reference: Key Imports

```python
from mcp_refcache import (
    # Core
    RefCache,
    CacheResponse,
    CacheReference,
    
    # Configuration
    PreviewConfig,
    PreviewStrategy,
    SizeMode,
    
    # Tokenizer (for token-based sizing)
    TiktokenAdapter,
    
    # Access control
    AccessPolicy,
    Permission,
    
    # Resolution utilities (usually handled by decorator)
    is_ref_id,
    resolve_refs,
    RefResolver,
    ResolutionResult,
)

from mcp_refcache.fastmcp import (
    cache_instructions,
    cached_tool_description,
    cache_guide_prompt,
    with_cache_docs,
)
```

---

## Quick Reference: Decorator Options

```python
@cache.cached(
    namespace="public",        # Namespace for isolation
    policy=AccessPolicy(...),  # Custom access control
    ttl=3600,                  # TTL in seconds (None = use cache default)
    max_size=500,              # Override cache default for size threshold
    resolve_refs=True,         # Resolve ref_ids in inputs (default: True)
    actor="agent",             # Actor for permission checks during resolution
)
```

---

## Ref_id Pattern

Ref_ids follow the pattern: `{cache_name}:{hex_hash}`

- Cache name: alphanumeric, hyphens, underscores, starts with letter
- Hash: 8+ hexadecimal characters

Examples:
- `finquant:2780226d27c57e49` ✅
- `my-cache:abc12345def` ✅
- `just-a-string` ❌ (no colon)
- `123cache:abc12345` ❌ (starts with number)