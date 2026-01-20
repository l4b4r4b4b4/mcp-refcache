# Task-01: Generate Project with FastMCP Template

> **Status**: 🔴 Not Started
> **Created**: 2024-12-28
> **Updated**: 2024-12-28

## Objective

Use cookiecutter with fastmcp-template to generate a new Real Estate Sustainability Analysis MCP server project with proper configuration and initial setup.

## Steps

### 1. Install Cookiecutter
- [ ] Install cookiecutter tool: `uv tool install cookiecutter`
- [ ] Verify installation works

### 2. Generate Project
- [ ] Run cookiecutter with fastmcp-template
- [ ] Configure project parameters:
  - `project_name`: "Real Estate Sustainability Analysis MCP"
  - `project_slug`: "real-estate-sustainability-mcp"
  - `project_description`: "MCP server for analyzing building sustainability metrics through Excel, PDF, and standardized frameworks (ESG, LEED, BREEAM, DGNB) with IFC integration"
  - `author_name`: [User's name]
  - `author_email`: [User's email]
  - `python_version`: "3.12"
  - `include_demo_tools`: "no" (clean start)
  - `include_langfuse`: "yes" (observability)
  - `github_username`: [User's GitHub username]

### 3. Initial Project Setup
- [ ] Navigate to generated project directory
- [ ] Run initial tests: `uv run pytest`
- [ ] Verify server starts: `uv run real-estate-sustainability-mcp stdio`
- [ ] Review generated structure and documentation

### 4. Configure mcp-refcache Integration
- [ ] Add mcp-refcache dependency: `uv add mcp-refcache`
- [ ] Configure RefCache in server setup
- [ ] Add basic cache configuration for development

### 5. Project Structure Customization
- [ ] Create tool module directories:
  - `app/tools/excel/`
  - `app/tools/pdf/`
  - `app/tools/sustainability/`
  - `app/tools/ifc_integration/`
- [ ] Update project README with sustainability analysis focus
- [ ] Configure development environment (VS Code/Zed settings)

## Acceptance Criteria

- [ ] New project generated successfully with cookiecutter
- [ ] All initial tests pass
- [ ] MCP server starts without errors
- [ ] mcp-refcache integration configured
- [ ] Tool module structure created
- [ ] Documentation updated for sustainability focus
- [ ] Development environment ready for implementation

## Notes

### Cookiecutter Command
```bash
cookiecutter gh:l4b4r4b4b4/fastmcp-template
```

### Expected Project Location
The new project should be generated outside the mcp-refcache repository, likely in a sibling directory or dedicated projects folder.

### Key Configuration Decisions
- **No demo tools**: Starting clean to avoid confusion with sustainability-specific tools
- **Include Langfuse**: Observability will be important for monitoring large data processing
- **Python 3.12**: Latest stable version for best performance and features

### Next Steps After Completion
Once this task is complete, we can proceed with implementing the individual toolsets (Excel, PDF, sustainability frameworks) in the newly generated project.
