# Redis Docker Example - Cross-Tool Reference Sharing

This example demonstrates cross-tool reference sharing between two MCP servers
using a shared Valkey (Redis-compatible) backend, all running in Docker containers.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Calculator    │     │  Data Analysis  │
│   MCP Server    │     │   MCP Server    │
│   (port 8001)   │     │   (port 8002)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │   Shared Redis Cache  │
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────┴──────┐
              │   Valkey    │
              │ (port 6379) │
              └─────────────┘
```

## Quick Start

### 1. Start all services

```bash
# From the mcp-refcache root directory
docker compose up -d

# View logs
docker compose logs -f
```

### 2. Verify services are running

```bash
# Check health status
docker compose ps

# Expected output:
# NAME                        STATUS                   PORTS
# mcp-refcache-calculator     Up (healthy)             0.0.0.0:8001->8001/tcp
# mcp-refcache-data-analysis  Up (healthy)             0.0.0.0:8002->8002/tcp
# mcp-refcache-valkey         Up (healthy)             0.0.0.0:6379->6379/tcp
```

### 3. Configure Zed IDE

Add to your `.zed/settings.json`:

```json
{
  "context_servers": {
    "calculator": {
      "settings": {
        "url": "http://localhost:8001/sse"
      }
    },
    "data-analysis": {
      "settings": {
        "url": "http://localhost:8002/sse"
      }
    }
  }
}
```

### 4. Test Cross-Tool Reference Sharing

In Zed's AI assistant:

```
1. Generate primes using calculator:
   → generate_primes(count=50)
   → Returns: {"ref_id": "calculator:abc123", "preview": [2, 3, 5, 7, ...]}

2. Analyze the primes using data-analysis (pass the ref_id):
   → analyze_data(data="calculator:abc123")
   → Returns: {"mean": 57.3, "median": 53, "std": 32.1, ...}

3. Transform the data:
   → transform_data(data="calculator:abc123", operation="normalize")
   → Returns: {"ref_id": "data-analysis:xyz789", ...}

4. List all cached references:
   → list_shared_cache()
   → Shows refs from both servers
```

## Available Tools

### Calculator Server (port 8001)

| Tool | Description |
|------|-------------|
| `calculate` | Evaluate mathematical expressions |
| `generate_primes` | Generate prime numbers (cached) |
| `generate_fibonacci` | Generate Fibonacci sequence (cached) |
| `generate_sequence` | Generate various sequences (cached) |
| `get_cached_result` | Retrieve cached results with pagination |
| `list_cached_keys` | List keys from this server |

### Data Analysis Server (port 8002)

| Tool | Description |
|------|-------------|
| `analyze_data` | Statistical analysis (mean, median, std, etc.) |
| `transform_data` | Transform data (normalize, scale, log, etc.) |
| `aggregate_data` | Combine multiple datasets |
| `create_sample_data` | Generate sample data |
| `get_cached_result` | Retrieve cached results with pagination |
| `list_shared_cache` | List all refs from all servers |

## Development

### Rebuild after code changes

```bash
docker compose build --no-cache
docker compose up -d
```

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f calculator
docker compose logs -f data-analysis
docker compose logs -f valkey
```

### Stop and cleanup

```bash
# Stop services
docker compose down

# Stop and remove volumes (clears Redis data)
docker compose down -v
```

### Run only Valkey (for local development)

```bash
# Start only Valkey
docker compose up -d valkey

# Run MCP servers locally
REDIS_HOST=localhost REDIS_PASSWORD=mcp-refcache-dev-password \
  python examples/redis-docker/calculator_server.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `valkey` | Redis/Valkey hostname |
| `REDIS_PORT` | `6379` | Redis/Valkey port |
| `REDIS_PASSWORD` | (required) | Redis/Valkey password |
| `REDIS_DB` | `0` | Redis database number |
| `MCP_PORT` | `8001`/`8002` | HTTP port for MCP server |

## Troubleshooting

### Services not starting

```bash
# Check if port is in use
lsof -i :8001
lsof -i :8002
lsof -i :6379

# View detailed logs
docker compose logs --tail=50 calculator
```

### Connection refused

Ensure Valkey is healthy before MCP servers start:

```bash
docker compose ps
# Valkey should show "Up (healthy)"
```

### Cache not shared between servers

Both servers must use the same Redis instance. Verify:

```bash
# Connect to Redis and check keys
docker exec -it mcp-refcache-valkey valkey-cli -a mcp-refcache-dev-password
> KEYS mcp-refcache:*
```

## Security Note

The default password `mcp-refcache-dev-password` is for development only.
For production deployments:

1. Use a strong, unique password
2. Enable Redis TLS/SSL
3. Use environment variables or secrets management
4. Restrict network access
