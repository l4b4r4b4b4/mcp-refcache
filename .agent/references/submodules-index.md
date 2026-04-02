# Submodule Reference Index

> Auto-generated for PR discoverability on branch `feat/monorepo-restructure`.
> Last updated: 2026-04-02

This monorepo uses git submodules as **references** to companion MCP server projects.
Submodules are kept by default (reference-first policy) — see `README.md` for rationale.

## Registered Submodules

### Example MCP Servers

| Path | Remote URL | Commit SHA | Branch | Purpose |
|------|-----------|------------|--------|---------|
| `examples/BundesMCP` | https://github.com/l4b4r4b4b4/BundesMCP | `b508e98` | `feat/refcache-sync-2026-04-02` | German federal data MCP server with mcp-refcache integration |
| `examples/bim2sim-mcp` | https://github.com/l4b4r4b4b4/bim2sim-mcp.git | `da1bede` | `feat/foundation-sync-2026-04-02` | BIM-to-simulation orchestration and workflow tools |
| `examples/fastmcp-template` | git@github.com:l4b4r4b4b4/fastmcp-template.git | `f6cc1f7` | `feat/refcache-sync-2026-04-02` | Starter template for FastMCP servers with refcache |
| `examples/finquant-mcp` | https://github.com/l4b4r4b4b4/finquant-mcp | `9dd14d1` | `feat/refcache-sync-2026-04-02` | Financial quantitative analysis MCP server |
| `examples/ifc-mcp` | git@github.com:AIS-AI-Team/ifc-mcp.git | `f7cc304` | `feature/jwt-supabase-auth` | IFC/BIM model processing MCP server |
| `examples/legal-mcp` | https://github.com/l4b4r4b4b4/legal-mcp | `59841ab` | `feat/refcache-sync-2026-04-02` | Legal document analysis with TEI embeddings |
| `examples/portfolio-mcp` | https://github.com/l4b4r4b4b4/portfolio-mcp.git | `dae3d7e` | `docs/enhance-readme` | Portfolio management and pricing MCP server |
| `examples/real-estate-sustainability-mcp` | https://github.com/l4b4r4b4b4/real-estate-sustainability-mcp.git | `67e7a1a` | `fix/schema-tests` | Real estate sustainability metrics and CRREM analysis |
| `examples/yt-mcp` | git@github.com:l4b4r4b4b4/yt-api-mcp.git | `d85d092` | `chore/mcp-refcache-sync-2026-04-02` | YouTube API with semantic search and transcript caching |

### Internal References

| Path | Remote URL | Commit SHA | Branch | Purpose |
|------|-----------|------------|--------|---------|
| `.agent/goals/04-Async-Timeout-Fallback/hatchet-reference` | https://github.com/hatchet-dev/hatchet.git | `15c8248` | `feat/refcache-sync-2026-04-02` | Hatchet task queue reference for async timeout patterns |

## Unregistered Local Repos

These directories contain git repositories that are **not** registered as submodules
(no remote URL configured). They remain as untracked local working directories:

| Path | Status | Notes |
|------|--------|-------|
| `examples/document-mcp` | local-only | DIN276 document classification server (needs remote) |
| `examples/optimize-mcp` | local-only | Convex optimization tools server (needs remote) |

## Maintenance Notes

- All dirty submodules were committed on pragmatic feature branches before pointer updates.
- `document-mcp` and `optimize-mcp` were removed from the git index (`git rm --cached`)
  because they have no remote URL and cannot function as proper submodule references.
  Their local content is preserved and committed on `chore/mcp-refcache-sync-2026-04-02`.
- To re-register them as submodules, first create GitHub repos and then:
  ```
  git submodule add <url> examples/document-mcp
  git submodule add <url> examples/optimize-mcp
  ```
