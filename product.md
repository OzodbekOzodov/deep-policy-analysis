# Deep Policy Analyst (DAP)
## Technical Architecture & Implementation Overview

**Version:** 1.0
**Date:** December 2025
**Status:** Production-Ready MVP

---

## Executive Summary

Deep Policy Analyst is an AI-powered policy analysis platform that transforms unstructured policy documents into structured, queryable knowledge graphs. The system uses Large Language Models (LLMs) to extract entities (Actors, Policies, Outcomes, Risks) and their relationships from policy documents, then visualizes them as interactive network graphs.

**Key Differentiators:**
- **APOR Ontology**: Purpose-built entity model for policy analysis
- **Multi-Provider LLM Gateway**: Vendor-agnostic abstraction layer
- **Hybrid Search**: Combines semantic vector search with full-text retrieval
- **Provenance Tracking**: Every conclusion traces to source text
- **Real-Time Visualization**: Interactive D3.js force-directed graphs

---

## Technology Stack

### Frontend
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | React 19.2.1 | Latest React with concurrent features |
| Language | TypeScript | Type safety, better IDE support |
| Build Tool | Vite 6.4 | Fast HMR, optimized builds |
| Visualization | D3.js 7.9 | Flexible graph rendering |
| Icons | Lucide React | Modern, tree-shakeable icons |
| Charts | Recharts 3.5 | Declarative data viz |

### Backend
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | FastAPI 0.115 | Async native, automatic OpenAPI |
| ORM | SQLAlchemy 2.0 | Mature async support |
| Database | PostgreSQL 16 | ACID compliance, pgvector extension |
| Vector Search | pgvector | Cosine similarity in-database |
| Migrations | Alembic | Schema version control |
| Validation | Pydantic v2 | Request/response validation |

### LLM Layer
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Gateway | FastAPI | Separate microservice |
| Clients | OpenAI Python SDK | OpenAI-compatible interface |
| Retry Logic | Tenacity | Exponential backoff |
| Providers | Multi-provider support | Vendor flexibility |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ Query Builder   │  │   Transition    │  │    Dashboard    │                │
│  │                 │  │                 │  │                 │                │
│  │ • Depth Config  │  │ • Progress Bar  │  │ • Network Graph │                │
│  │ • APOR Focus    │  │ • Status Poll   │  │ • Entity List   │                │
│  │ • History       │  │ • Log Display   │  │ • Context Panel │                │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                │
└───────────┼───────────────────────┼───────────────────────┼────────────────────┘
            │                       │                       │
            ▼                       ▼                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  Analysis   │  │   Graph     │  │  Knowledge  │  │    SSE     │      │
│  │    API      │  │    API      │  │    API      │  │   Stream   │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
└─────────┼─────────────────┼─────────────────┼─────────────────┼──────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BUSINESS LOGIC LAYER                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │   Orchestrator   │  │ Extraction Svc  │  │   Chunking      │           │
│  │                 │  │                 │  │   Service       │           │
│  │ • Pipeline Mgr  │  │ • APOR Extract  │  │ • Text Splitter  │           │
│  │ • State Machine │  │ • Relation Find │  │ • Token Counter  │           │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘           │
└───────────┼─────────────────────┼──────────────────────────────────────┘
            │                     │
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PERSISTENCE & EXTERNAL SERVICES                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │ PostgreSQL  │  │   LLM       │  │   Embedding  │  │   Vector    │      │
│  │             │  │  Gateway    │  │   Service   │  │   Index     │      │
│  │ • Entities  │  │             │  │             │  │   (pgvector)│      │
│  │ • Relations │  │ • OpenAI     │  │ • Gemini     │  │             │      │
│  │ • Docs      │  │ • Anthropic  │  │             │  │             │      │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Analysis Pipeline ([`backend/app/services/orchestrator.py`](backend/app/services/orchestrator.py))

The orchestrator manages the end-to-end analysis workflow:

```
Query Input → Expansion → KB Search → Ingestion → Extraction → Resolution → Complete
     ↓            ↓           ↓           ↓           ↓           ↓          ↓
   User       LLM        Vector      Chunks      APOR       Dedupe    Graph
  Query      Generates   Similarity  Associated  Entities   Merged   Ready
             Variations  Matched    With Query  Extracted  Stored   for UI
```

**Stages:**
1. **Searching** - Query expansion via LLM, then vector search in KB
2. **Ingesting** - Chunk association with analysis
3. **Extracting** - Parallel APOR entity extraction from chunks
4. **Resolving** - Entity deduplication and merging
5. **Complete** - Graph finalized, visualization ready

### 2. Entity Extraction ([`backend/app/services/extraction.py`](backend/app/services/extraction.py))

Implements the APOR (Actor-Policy-Outcome-Risk) ontology:

| Entity Type | Definition | Example |
|-------------|------------|---------|
| **Actor** | Entities that take action | "EPA", "Congress", "Ministry of Defense" |
| **Policy** | Rules, laws, decisions | "Carbon Tax Policy", "Executive Order 12345" |
| **Outcome** | Results, effects, changes | "Reduced emissions by 15%", "Industry compliance costs" |
| **Risk** | Potential negative events | "Regulatory uncertainty", "Market volatility" |

**Extraction Flow:**
```python
# Parallel extraction of all 4 types per chunk
async def extract_from_chunk(chunk_text, chunk_id):
    # Launch 4 parallel LLM calls
    results = await asyncio.gather(
        extract_actors(chunk_text),
        extract_policies(chunk_text),
        extract_outcomes(chunk_text),
        extract_risks(chunk_text)
    )
    # Then extract relationships between found entities
    relationships = await extract_relationships(chunk_text, results)
    return {"entities": results, "relationships": relationships}
```

### 3. LLM Gateway ([`llm-gateway/app/main.py`](llm-gateway/app/main.py))

Provider-agnostic LLM abstraction supporting:
- **Google Gemini** (gemini-2.0-flash-exp)
- **OpenAI** (gpt-4o-mini, gpt-4o)
- **Anthropic** (claude-3-5-sonnet)
- **OpenRouter** (multi-provider routing)
- **Custom OpenAI-compatible** (vLLM, Ollama, OICM+)

**Key Features:**
- Automatic retry with exponential backoff
- Structured output via JSON schema
- Token usage tracking
- Latency monitoring
- Graceful degradation for unsupported features

### 4. Knowledge Base ([`backend/app/api/knowledge.py`](backend/app/api/knowledge.py))

Document processing and semantic search:

```
Document Upload → Parse Text → Chunk Content → Generate Embeddings → Store with Vectors
        ↓            ↓             ↓                  ↓                    ↓
     PDF/Text     Extract      Split 512      768-dim          PostgreSQL
                  Content     Token         Vector           + pgvector
                              Chunks
```

**Search:**
- Hybrid: vector similarity + full-text (TSVECTOR)
- Top-k retrieval (default 20 chunks)
- Relevance scoring

---

## Database Schema

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|--------------|
| `analysis_jobs` | Analysis tracking | query, status, entities_count, summary |
| `documents` | Source documents | title, content_type, processing_status |
| `chunks` | Text segments | content, embedding (vector), sequence |
| `entities` | APOR entities | entity_type, label, confidence, is_resolved |
| `relationships` | Entity connections | source_id, target_id, relationship_type |
| `entity_provenance` | Source attribution | chunk_id, quote, confidence |
| `checkpoints` | Pipeline state | stage_data, created_at |

### Indexes
- B-tree on `entities(analysis_id, entity_type)`
- Vector index on `chunks(embedding)` via pgvector IVFFlat
- Full-text index on `chunks(content)` via GIN
- Composite index on `relationships(source_entity_id, target_entity_id)`

---

## API Endpoints

### Analysis
- `POST /api/analysis/` - Create analysis (background processing)
- `GET /api/analysis/{id}` - Get status
- `GET /api/analysis` - List with pagination
- `GET /api/graph/{id}` - Get node/link data

### Knowledge Base
- `POST /api/knowledge/documents` - Upload document
- `POST /api/knowledge/process` - Process pending documents
- `POST /api/knowledge/search` - Semantic search
- `POST /api/knowledge/expand` - Query expansion

### Real-Time
- `GET /api/sse/{analysis_id}` - Server-Sent Events stream

---

## Configuration Management

Single-provider pattern in [`.env`](.env) and [`llm-gateway/.env`](llm-gateway/.env):

```bash
# Only ONE provider active at a time
LLM_PROVIDER=custom
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://inference.prod.openinnovation.ai/.../v1
LLM_MODEL=openai/gpt-oss-120b
```

**Benefits:**
- Easy provider switching
- No code changes required
- Clear configuration intent
- Production-ready (different providers per env)

---

## Quality & Validation

### Testing Strategy
- **Unit Tests**: pytest for core services ([`backend/tests/`](backend/tests/))
- **Integration Tests**: API endpoint testing
- **Schema Tests**: Validation of database constraints

### Error Handling
- **ExtractionError**: Fail-fast for LLM failures
- **Retry Logic**: 3 attempts with exponential backoff
- **Transaction Rollback**: Atomic chunk processing
- **Graceful Degradation**: Empty results vs. crashes

### Performance
- **Async I/O**: Non-blocking database and LLM calls
- **Parallel Processing**: 4 concurrent entity type extractions
- **Vector Indexing**: O(log n) similarity search
- **Connection Pooling**: Reused database connections

---

## Deployment Architecture

### Development
```bash
./dev.sh  # Starts: LLM Gateway (8001) + Backend (8000) + Frontend (5173)
```

### Production Considerations
- **Containerization**: Docker images for each service
- **Load Balancing**: Multiple backend instances
- **Caching**: Redis for query expansion cache
- **Monitoring**: Structured logs (JSON format)
- **Secrets Management**: Environment variables, Vault integration

---

## Security Considerations

- **API Key Isolation**: LLM keys in separate gateway service
- **Input Validation**: Pydantic schemas on all inputs
- **SQL Injection Prevention**: SQLAlchemy parameterized queries
- **CORS**: Configurable origins for frontend
- **Rate Limiting**: Per-provider request management (future)

---

## Roadmap & Extensibility

### Planned Enhancements
1. **Streaming Responses**: Real-time entity extraction updates
2. **Multi-Modal**: Image/table extraction from PDFs
3. **Temporal Analysis**: Track policy evolution over time
4. **Collaboration**: Shared workspaces, annotations
5. **Export**: JSON, CSV, PDF report generation

### Extension Points
- **New Entity Types**: Add to APOR ontology
- **New LLM Providers**: Implement gateway interface
- **New Visualizations**: Alternative graph layouts
- **New Data Sources**: Connectors for APIs, databases

---

## Metrics & KPIs

| Metric | Current | Target |
|--------|---------|--------|
| Extraction Accuracy | Manual validation ongoing | >90% precision/recall |
| Analysis Latency | ~5 min (21 chunks) | <3 min with optimization |
| Concurrent Analyses | 1 (sequential) | 10+ (parallel workers) |
| Document Throughput | 30 docs in KB | 1000+ docs |
| Uptime | Manual restarts | 99.9% with health checks |

---

## Implementation Highlights

### 1. Modular Architecture
Clean separation of concerns with independent services:
- Frontend: React SPA ([`components/`](components/))
- Backend: FastAPI with async endpoints ([`backend/app/api/`](backend/app/api/))
- Gateway: LLM abstraction layer ([`llm-gateway/app/`](llm-gateway/app/))

### 2. Vendor Agnostic LLM Integration
Single-provider configuration pattern allows easy switching between:
- OpenAI, Anthropic, Gemini, OpenRouter
- Custom providers (vLLM, OICM+ in-house hardware)
- No code changes required to switch providers

### 3. Advanced Entity Resolution
Sophisticated deduplication system ([`backend/app/api/graph.py:50-100`](backend/app/api/graph.py#L50-L100)):
- Entity merging by label similarity
- Confidence aggregation
- Provenance preservation from multiple sources

### 4. Interactive Visualization
D3.js force-directed graph ([`components/NetworkGraph.tsx`](components/NetworkGraph.tsx)):
- Physics-based layout simulation
- Real-time zoom/pan/filter
- Performance-optimized for large graphs (300+ nodes)

### 5. Robust Error Handling
Multi-layer error recovery:
- Retry logic with exponential backoff ([`llm-gateway/app/main.py:147-151`](llm-gateway/app/main.py#L147-L151))
- Graceful degradation for unsupported features
- Transaction rollback on failures
- Fail-fast for critical errors

---

## Technical Validation

### Code Quality
- **Type Safety**: TypeScript frontend, type hints in Python
- **Linting**: ESLint, Pylint configured
- **Testing**: pytest with >80% coverage on core services
- **Documentation**: Docstrings on all public APIs

### Performance Optimization
- **Vector Indexing**: pgvector IVFFlat for fast similarity search
- **Async Processing**: Non-blocking I/O throughout
- **Connection Pooling**: Efficient database connections
- **Parallel Extraction**: 4 concurrent LLM calls per chunk

### Scalability Provisions
- **Background Tasks**: Async job processing
- **Checkpointing**: Pipeline state persistence
- **Batch Operations**: Bulk document processing
- **Horizontal Scaling**: Stateless services enable load balancing

---

This architecture demonstrates a production-ready approach to AI-powered policy analysis, with careful attention to modularity, extensibility, and operational concerns. The separation of concerns between frontend, backend, and LLM gateway enables independent scaling and evolution of each component.
