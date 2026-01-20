# Goal: Real Estate Sustainability Analysis MCP Server

> **Status**: 🔴 Not Started
> **Priority**: P1 (High)
> **Created**: 2024-12-28
> **Updated**: 2024-12-28

## Overview

Build a comprehensive Real Estate Sustainability Analysis MCP server using fastmcp-template and mcp-refcache integration. The server will provide tools for analyzing building sustainability metrics through Excel file processing, PDF document analysis with semantic search, and standardized sustainability framework assessments (ESG, BREEAM/LEED, DGNB). Integration with ifc-mcp will enable building geometry and property data correlation with sustainability metrics.

## Success Criteria

- [ ] **Excel Toolset**: Complete Excel file handling with mcp-refcache integration for large datasets
- [ ] **PDF Analysis**: Full PDF processing with Chroma-powered semantic search and metadata extraction
- [ ] **Sustainability Frameworks**: Implement ESG, LEED, BREEAM, and DGNB assessment tools
- [ ] **IFC Integration**: Successfully integrate with ifc-mcp for building data correlation
- [ ] **Production Ready**: Docker deployment, CI/CD, and comprehensive documentation
- [ ] **Type Safe**: Full type hints with Pydantic models for all APIs
- [ ] **Test Coverage**: ≥80% test coverage with integration tests
- [ ] **Performance**: Handle large datasets efficiently via mcp-refcache references

## Context & Background

Real estate sustainability analysis requires processing diverse data sources:
- **Excel files**: Energy consumption, cost data, building metrics
- **PDF documents**: Certificates, audit reports, compliance documents
- **Building data**: IFC geometry/properties from ifc-mcp
- **Standards compliance**: Multiple sustainability frameworks (ESG, LEED, BREEAM, DGNB)

Current tools are fragmented and don't handle large datasets efficiently. This MCP server will provide a unified interface for sustainability consultants, developers, and facility managers.

## Constraints & Requirements

**Hard Requirements**:
- Use fastmcp-template as the project foundation
- Integrate mcp-refcache for handling large data without context limits
- Support IFC-MCP integration for building data correlation
- Implement semantic search with Chroma for PDF content
- Follow all .rules guidelines (TDD, type safety, documentation)

**Soft Requirements**:
- Support multiple sustainability frameworks simultaneously
- Provide preview generation for large analysis results
- Enable batch processing of multiple buildings/documents
- Support multilingual content (German/English for DGNB)

**Out of Scope**:
- Direct IFC file parsing (use ifc-mcp integration instead)
- Custom sustainability framework creation
- Real-time data streaming or live building sensors

## Approach

**Phase 1: Project Foundation**
1. Use cookiecutter with fastmcp-template to generate base project
2. Configure mcp-refcache integration
3. Set up development environment with proper tooling

**Phase 2: Core Toolsets**
1. **Excel Toolset**: Build on existing Excel MCP, enhance with mcp-refcache
2. **PDF Toolset**: Implement with PyPDF2/pdfplumber + Chroma semantic search
3. **Sustainability Frameworks**: Implement assessment logic for each standard

**Phase 3: Integration & Testing**
1. Integrate with ifc-mcp for building data correlation
2. Implement cross-toolset workflows
3. Comprehensive testing and documentation

**Phase 4: Production Deployment**
1. Docker containerization
2. CI/CD pipeline setup
3. Performance optimization

## Tasks

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| Task-01 | Generate project with fastmcp-template | 🔴 | - |
| Task-02 | Excel toolset implementation | 🔴 | Task-01 |
| Task-03 | PDF analysis with Chroma integration | 🔴 | Task-01 |
| Task-04 | Sustainability frameworks (ESG, LEED, BREEAM, DGNB) | 🔴 | Task-01 |
| Task-05 | IFC-MCP integration and correlation tools | 🔴 | Task-01, Task-04 |
| Task-06 | Cross-toolset workflows and orchestration | 🔴 | Task-02, Task-03, Task-04 |
| Task-07 | Testing, documentation, and production deployment | 🔴 | All previous |

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Sustainability framework complexity | High | Medium | Start with well-documented standards (LEED), add others iteratively |
| Large PDF processing performance | High | Medium | Use mcp-refcache references + streaming for large documents |
| IFC-MCP integration complexity | Medium | Low | Study existing ifc-mcp API, implement gradual integration |
| Chroma semantic search accuracy | Medium | Medium | Implement fallback to text search, tune embedding models |

## Dependencies

**Upstream**:
- fastmcp-template (cookiecutter generation)
- mcp-refcache library (reference-based caching)
- ifc-mcp server (building data integration)

**Downstream**:
- Real estate analysis workflows
- Sustainability reporting pipelines
- Building certification processes

## Notes & Decisions

### Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2024-12-28 | Use Chroma for PDF semantic search | Mature vector database, good Python integration |
| 2024-12-28 | Start with LEED, BREEAM, DGNB, ESG frameworks | Common standards with clear documentation |
| 2024-12-28 | Integrate via ifc-mcp rather than direct IFC parsing | Leverage existing, mature IFC processing |

### Open Questions

- [ ] Which specific Excel MCP should we use as starting point?
- [ ] BREEAM vs CREAM clarification - which sustainability standard?
- [ ] Target document languages (German, English, others)?
- [ ] Preferred embedding model for Chroma semantic search?
- [ ] IFC-MCP integration patterns - direct API calls or shared data references?
- [ ] User authentication/authorization requirements for sensitive building data?

## Architecture Overview

```
Real Estate Sustainability MCP Server
├── Excel Toolset
│   ├── Data import/export (openpyxl, pandas)
│   ├── Large dataset handling (mcp-refcache)
│   └── Energy/cost/metrics processing
├── PDF Analysis Toolset
│   ├── Content extraction (PyPDF2, pdfplumber)
│   ├── Metadata processing
│   ├── Semantic search (Chroma + embeddings)
│   └── Document classification
├── Sustainability Frameworks
│   ├── ESG assessment tools
│   ├── LEED certification analysis
│   ├── BREEAM evaluation
│   └── DGNB compliance checking
├── IFC Integration
│   ├── ifc-mcp API client
│   ├── Building data correlation
│   └── Geometry-sustainability mapping
└── Orchestration
    ├── Cross-toolset workflows
    ├── Batch processing
    └── Report generation
```

## References

- [FastMCP Template](../../examples/fastmcp-template/README.md)
- [mcp-refcache Documentation](../../README.md)
- [IFC-MCP Server](../../examples/ifc-mcp/README.md)
- [LEED Rating System](https://www.usgbc.org/leed)
- [BREEAM Standards](https://bregroup.com/products/breeam/)
- [DGNB System](https://www.dgnb.de/en/)
- [EU ESG Taxonomy](https://finance.ec.europa.eu/sustainable-finance/tools-and-standards/eu-taxonomy-sustainable-activities_en)
- [Chroma Vector Database](https://docs.trychroma.com/)
