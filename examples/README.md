# mcp-refcache Examples

This directory contains example MCP servers demonstrating how to use `mcp-refcache` with FastMCP.

## Scientific Calculator (`mcp_server.py`)

A fully functional MCP server showcasing all RefCache capabilities through a scientific calculator interface.

### Features Demonstrated

| Feature | Tool | Description |
|---------|------|-------------|
| **Basic Caching** | `calculate` | Cache computation results |
| **Large Results** | `generate_sequence` | Return references + previews for big data |
| **Pagination** | `get_cached_result` | Page through cached sequences/matrices |
| **Matrix Operations** | `matrix_operation` | Linear algebra with cached results |
| **Private Computation** | `store_secret`, `compute_with_secret` | EXECUTE without READ permission |
| **Cache Statistics** | `list_cache_stats` | Inspect cache configuration |

### Prerequisites

Install the MCP extra:

```bash
# Using uv (recommended)
uv add "mcp-refcache[mcp]"

# Using pip
pip install "mcp-refcache[mcp]"
```

### Running the Server

#### For Claude Desktop (stdio transport)

```bash
# From the repository root
python examples/mcp_server.py
```

#### For Web Clients / Debugging (SSE transport)

```bash
# Run on default port 8000
python examples/mcp_server.py --transport sse

# Custom host and port
python examples/mcp_server.py --transport sse --host 0.0.0.0 --port 3000
```

### Claude Desktop Configuration

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "calculator": {
      "command": "python",
      "args": ["/absolute/path/to/mcp-refcache/examples/mcp_server.py"]
    }
  }
}
```

**Using uv (recommended for dependency management):**

```json
{
  "mcpServers": {
    "calculator": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/absolute/path/to/mcp-refcache",
        "python", "examples/mcp_server.py"
      ]
    }
  }
}
```

### Example Prompts to Try

Once connected, try these prompts in Claude:

#### Basic Calculations
> Calculate sin(pi/2) + sqrt(16)

> What's the factorial of 20?

#### Sequence Generation
> Generate the first 100 Fibonacci numbers

> Show me the first 50 prime numbers

> Give me page 2 of those prime numbers, 10 per page

#### Matrix Operations
> Calculate the determinant of [[1, 2], [3, 4]]

> Multiply these matrices: [[1, 0], [0, 1]] and [[5, 6], [7, 8]]

#### Private Computation (Secrets)
> Store a secret value of 42 called "my_constant"

> Now compute x * 2 + 1 using that secret (the agent shouldn't reveal the actual value)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Desktop                          │
│                    (or other MCP client)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (stdio or SSE)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastMCP Server                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    mcp_server.py                       │  │
│  │                                                        │  │
│  │  @mcp.tool                                             │  │
│  │  def calculate(...)  ─────────────┐                    │  │
│  │  async def generate_sequence(...) │                    │  │
│  │  def store_secret(...)            │                    │  │
│  │  def compute_with_secret(...)     │                    │  │
│  │                                   ▼                    │  │
│  │                          ┌───────────────┐             │  │
│  │                          │   RefCache    │             │  │
│  │                          │  - Caching    │             │  │
│  │                          │  - Previews   │             │  │
│  │                          │  - ACL        │             │  │
│  │                          │  - Pagination │             │  │
│  │                          └───────────────┘             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Concepts

#### Reference-Based Returns

Instead of returning large data directly:

```python
# Without RefCache - dumps everything into context
@mcp.tool
def generate_primes(count: int) -> list[int]:
    return list_of_10000_primes  # 💥 Floods agent context

# With RefCache - returns reference + preview
@mcp.tool
def generate_primes(count: int) -> dict:
    ref = cache.set("primes", list_of_10000_primes)
    response = cache.get(ref.ref_id)
    return {
        "ref_id": ref.ref_id,
        "preview": response.preview,  # [2, 3, 5, 7, ... and 9996 more]
        "total_items": 10000,
    }
```

#### Private Computation

Agents can use values without seeing them:

```python
# Store with EXECUTE-only permission
secret_policy = AccessPolicy(
    user_permissions=Permission.FULL,      # Human can see
    agent_permissions=Permission.EXECUTE,  # Agent can use, not read
)

cache.set("api_key", secret_value, policy=secret_policy)

# Later, in compute_with_secret:
# - System actor resolves the value (has full access)
# - Agent never sees the actual value
# - Computation result is returned
```

#### Pagination

Large cached values can be paginated:

```python
# First call returns preview
response = cache.get(ref_id)
# response.preview = [1, 1, 2, 3, 5, 8, ...]
# response.total_items = 1000

# Get specific page
response = cache.get(ref_id, page=5, page_size=20)
# response.preview = [...items 80-99...]
# response.page = 5
# response.total_pages = 50
```

### Troubleshooting

#### "FastMCP is not installed"

Install the MCP extra:
```bash
uv add "mcp-refcache[mcp]"
```

#### "Permission denied" when accessing secrets

Secrets are stored with EXECUTE-only permission for agents. This is intentional - agents can use them in `compute_with_secret` but cannot read them directly with `get_cached_result`.

#### SSE transport not connecting

Check that:
1. The port isn't already in use
2. Firewall allows the connection
3. You're connecting to the correct host/port

### Extending the Example

To add new tools:

```python
@mcp.tool
async def my_new_tool(param: str, ctx: Context) -> dict:
    """Tool description for the agent."""
    # Do computation
    result = expensive_computation(param)
    
    # Cache large results
    ref = cache.set(f"my_tool_{param}", result, namespace="public")
    response = cache.get(ref.ref_id)
    
    # Log via context
    await ctx.info(f"Computed result, cached as {ref.ref_id}")
    
    return {
        "ref_id": ref.ref_id,
        "preview": response.preview,
        "total_items": response.total_items,
    }
```

## More Examples (Coming Soon)

- `document_workspace.py` - Document management with namespaces
- `financial_analyzer.py` - Portfolio analysis with FinQuant integration
- `multi_user_chat.py` - Session-based caching for chat applications