# DAP System Architecture — Technical Plan

## Overview

This document defines the technical architecture for the Deep Analysis Platform, covering database choices, prompt expansion, agentic orchestration, and knowledge base management.

## Design Decisions

### 1. Vector/Graph Database: pgvector (PostgreSQL Extension)

**Choice: pgvector over Qdrant/Pinecone**

Reasoning:
- Already using PostgreSQL for relational data
- One database to manage, not two
- pgvector handles 1M+ vectors adequately for our scale
- No additional service to deploy/maintain
- Can migrate to dedicated vector DB later if needed
- Simpler local development (just Postgres)

What we lose:
- Qdrant has better filtering and hybrid search
- Pinecone has managed scaling
- Both have more vector-specific optimizations

For MVP with <100k documents, pgvector is sufficient. Migration path to Qdrant is straightforward if we hit scale limits.

**Implementation:**
```sql
-- Enable extension
CREATE EXTENSION vector;

-- Add embedding column to chunks table
ALTER TABLE chunks ADD COLUMN embedding vector(1536);

-- Create index for similarity search
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 2. Prompt Expansion System

**Problem:** Users write short, vague queries like "China chips" but mean complex research questions spanning multiple angles.

**Solution:** Query expansion pipeline that generates 10-20 search variations before retrieval.

**Expansion Types:**

1. **Synonym Expansion** — Replace key terms with alternatives
   - "China chips" → "China semiconductors", "PRC integrated circuits", "Chinese chip manufacturing"

2. **Aspect Expansion** — Break into sub-questions
   - "China chips" → "China chip manufacturing capacity", "China chip import dependency", "China chip export restrictions"

3. **Entity Expansion** — Add specific entities
   - "China chips" → "SMIC production", "Huawei chip supply", "YMTC memory chips"

4. **Temporal Expansion** — Add time context
   - "China chips" → "China chips 2024", "China semiconductor policy recent", "chip war timeline"

5. **Relationship Expansion** — Add connection queries
   - "China chips" → "US China chip restrictions", "Taiwan China semiconductor", "China chip self-sufficiency goals"

**Pipeline:**
```
User Query
    │
    ▼
┌─────────────────────────┐
│   Query Analyzer        │  Identify: entities, topics, implicit questions
│   (LLM Call #1)         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Query Expander        │  Generate 10-20 variations
│   (LLM Call #2)         │  Output: list of search queries
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Parallel Retrieval    │  Search knowledge base with ALL variations
│   (Vector Search)       │  Aggregate and deduplicate results
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Relevance Ranking     │  Score chunks by frequency across queries
│   (Signal Amplification)│  Chunks found by multiple queries rank higher
└───────────┬─────────────┘
            │
            ▼
    Top K Chunks for Extraction
```

**LLM Prompt for Expansion:**
```
Given this research query: "{user_query}"

Generate 15 search variations that would help find relevant information. Include:
- Synonym variations (different terms for same concepts)
- Aspect variations (specific angles or sub-questions)  
- Entity variations (specific organizations, people, policies mentioned or implied)
- Temporal variations (time-specific versions)
- Relationship variations (connections between entities)

Output as JSON array of strings.
```

### 3. Agentic Orchestration

**Principles:**

1. **Fallback Chains** — If one approach fails, try alternatives
2. **Signal Amplification** — Repeated patterns increase confidence
3. **Self-Correction** — Detect poor results and retry
4. **Graceful Degradation** — Always return something useful

**Agent Types:**

```
RETRIEVAL AGENTS
├── VectorSearchAgent      Primary: semantic search via embeddings
├── KeywordSearchAgent     Fallback: full-text search if vectors miss
└── WebSearchAgent         Fallback: fetch new content if KB insufficient

EXTRACTION AGENTS  
├── APORExtractor          Primary: multi-pass APOR extraction
├── SimpleExtractor        Fallback: single-pass if rate limited
└── RuleBasedExtractor     Fallback: regex/NER if LLM unavailable

SYNTHESIS AGENTS
├── ReportGenerator        Primary: full APOR report
├── SummaryGenerator       Fallback: brief summary if report fails
└── BulletGenerator        Fallback: key points only
```

**Orchestration Logic:**

```python
class AgentOrchestrator:
    async def run_with_fallback(self, agents: list, input_data: dict) -> Result:
        """Try agents in order until one succeeds."""
        errors = []
        for agent in agents:
            try:
                result = await agent.run(input_data)
                if self.is_valid_result(result):
                    return result
                errors.append(f"{agent.name}: Invalid result")
            except Exception as e:
                errors.append(f"{agent.name}: {str(e)}")
                continue
        
        # All failed - return degraded result
        return DegradedResult(errors=errors, partial_data=self.best_effort(input_data))
    
    def amplify_signals(self, extractions: list[ExtractionResult]) -> list[Entity]:
        """Boost confidence for entities found multiple times."""
        entity_counts = Counter()
        entity_data = {}
        
        for extraction in extractions:
            for entity in extraction.entities:
                key = self.normalize_entity_key(entity)
                entity_counts[key] += 1
                if key not in entity_data:
                    entity_data[key] = entity
                else:
                    # Merge provenance
                    entity_data[key].provenance.extend(entity.provenance)
        
        # Boost confidence based on frequency
        for key, count in entity_counts.items():
            if count >= 3:
                entity_data[key].confidence = min(100, entity_data[key].confidence + 15)
            elif count >= 2:
                entity_data[key].confidence = min(100, entity_data[key].confidence + 8)
        
        return list(entity_data.values())
```

**Retry Strategy:**

```python
class RetryPolicy:
    def __init__(self):
        self.max_retries = 3
        self.backoff_base = 2  # seconds
    
    async def execute(self, func, *args, **kwargs):
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except RateLimitError:
                wait = self.backoff_base ** attempt
                await asyncio.sleep(wait)
                last_error = "Rate limited"
            except TimeoutError:
                # Try with shorter timeout next time
                kwargs['timeout'] = kwargs.get('timeout', 60) * 0.7
                last_error = "Timeout"
            except InvalidResponseError as e:
                # Try with different temperature
                kwargs['temperature'] = kwargs.get('temperature', 0.2) + 0.1
                last_error = str(e)
        
        raise ExhaustedRetriesError(last_error)
```

### 4. Knowledge Base Architecture

**Concept:** The knowledge base grows over time as users add documents and system fetches web content. Each query searches across all accumulated knowledge.

**Document Lifecycle:**

```
INGESTION
    │
    ├── PDF Upload ──────────────────────────────────┐
    │                                                │
    ├── Text Paste ──────────────────────────────────┤
    │                                                │
    ├── Web Search Result ───────────────────────────┤
    │                                                ▼
    │                                    ┌─────────────────────┐
    │                                    │   Document Store    │
    │                                    │   (raw content)     │
    │                                    └──────────┬──────────┘
    │                                               │
    │                                               ▼
    │                                    ┌─────────────────────┐
    │                                    │   Parser Service    │
    │                                    │   - PDF → text      │
    │                                    │   - HTML → text     │
    │                                    │   - Metadata extract│
    │                                    └──────────┬──────────┘
    │                                               │
    │                                               ▼
    │                                    ┌─────────────────────┐
    │                                    │   Chunker Service   │
    │                                    │   - Split text      │
    │                                    │   - Overlap chunks  │
    │                                    │   - Track position  │
    │                                    └──────────┬──────────┘
    │                                               │
    │                                               ▼
    │                                    ┌─────────────────────┐
    │                                    │  Embedding Service  │
    │                                    │  - Generate vectors │
    │                                    │  - text-embedding-3 │
    │                                    └──────────┬──────────┘
    │                                               │
    │                                               ▼
    │                                    ┌─────────────────────┐
    │                                    │   Vector Store      │
    │                                    │   (pgvector)        │
    │                                    └─────────────────────┘

RETRIEVAL
    │
    User Query
    │
    ▼
┌─────────────────────┐
│  Query Expansion    │
│  (10-20 variations) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Embedding Service  │  Embed each query variation
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Vector Search      │  Search with all variations
│  (pgvector)         │  Aggregate results
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Chunk Retrieval    │  Fetch full chunk text
│  (PostgreSQL)       │  Include metadata
└──────────┬──────────┘
           │
           ▼
    Retrieved Chunks (for extraction)
```

**Knowledge Base Tables:**

```sql
-- Extend existing schema

-- Sources: where documents come from
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,  -- 'upload', 'web_search', 'paste'
    url TEXT,
    title VARCHAR(500),
    author VARCHAR(255),
    publish_date DATE,
    fetch_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Documents linked to sources
ALTER TABLE documents ADD COLUMN source_id UUID REFERENCES sources(id);
ALTER TABLE documents ADD COLUMN is_in_knowledge_base BOOLEAN DEFAULT true;

-- Chunks with embeddings
ALTER TABLE chunks ADD COLUMN embedding vector(1536);
ALTER TABLE chunks ADD COLUMN is_indexed BOOLEAN DEFAULT false;

-- Index for vector similarity search
CREATE INDEX chunks_embedding_idx ON chunks 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full-text search index (fallback)
ALTER TABLE chunks ADD COLUMN search_vector tsvector;
CREATE INDEX chunks_fts_idx ON chunks USING gin(search_vector);

-- Query expansion cache (avoid regenerating for same queries)
CREATE TABLE query_expansions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_query TEXT NOT NULL,
    query_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 of normalized query
    expansions JSONB NOT NULL,  -- Array of expanded queries
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 5. System Components

**Complete Service Map:**

```
FRONTEND (React + TypeScript + Vite)
│
├── Pages
│   ├── QueryBuilderPage      Entry point, query input
│   ├── AnalysisPage          Progress + results view
│   └── HistoryPage           Past analyses
│
├── Components
│   ├── NetworkGraph          D3 force-directed APOR graph
│   ├── EntityDetailPanel     Node details + provenance
│   ├── ReportViewer          APOR-structured report
│   └── ProgressDashboard     Real-time status
│
└── Services
    ├── api.ts                REST client
    └── sse.ts                Server-sent events client


BACKEND (FastAPI + Python)
│
├── API Layer (app/api/)
│   ├── analysis.py           Create/get analysis jobs
│   ├── documents.py          Upload/manage documents
│   ├── knowledge.py          Knowledge base management
│   ├── graph.py              Graph retrieval
│   └── sse.py                Progress streaming
│
├── Services (app/services/)
│   ├── orchestrator.py       Pipeline coordination
│   ├── ingestion.py          Document parsing + chunking
│   ├── embedding.py          Vector generation
│   ├── retrieval.py          Knowledge base search
│   ├── expansion.py          Query expansion
│   ├── extraction.py         APOR extraction
│   ├── resolution.py         Entity deduplication
│   ├── synthesis.py          Report generation
│   └── checkpoints.py        State snapshots
│
├── Agents (app/agents/)
│   ├── base.py               Base agent class
│   ├── retrieval/
│   │   ├── vector_agent.py   Semantic search
│   │   ├── keyword_agent.py  Full-text search
│   │   └── web_agent.py      External web search
│   ├── extraction/
│   │   ├── apor_agent.py     Multi-pass extraction
│   │   └── simple_agent.py   Single-pass fallback
│   └── synthesis/
│       ├── report_agent.py   Full report
│       └── summary_agent.py  Brief summary fallback
│
├── Clients (app/clients/)
│   ├── llm.py                LLM Gateway client
│   └── embedding.py          Embedding API client
│
├── Prompts (app/prompts/)
│   ├── expansion.py          Query expansion prompts
│   ├── extraction.py         APOR extraction prompts
│   └── synthesis.py          Report generation prompts
│
└── Workers (app/workers/)
    └── tasks.py              Background job definitions


LLM GATEWAY (FastAPI + Python)
│
├── Providers
│   ├── gemini.py             Google Gemini
│   ├── openai.py             OpenAI (future)
│   └── anthropic.py          Claude (future)
│
├── Router
│   └── model_router.py       Select provider based on task
│
└── Middleware
    ├── rate_limiter.py       Request throttling
    ├── token_counter.py      Usage tracking
    └── retry_handler.py      Automatic retries


DATABASE (PostgreSQL + pgvector)
│
├── Tables
│   ├── analysis_jobs         Job state and metadata
│   ├── sources               Document origins
│   ├── documents             Raw content
│   ├── chunks                Split text + embeddings
│   ├── entities              Extracted APOR nodes
│   ├── entity_provenance     Source quotes
│   ├── relationships         Entity connections
│   ├── checkpoints           Pipeline snapshots
│   ├── progress_events       SSE data
│   └── query_expansions      Cached expansions
│
└── Extensions
    └── pgvector              Vector similarity search
```

### 6. Data Flow: Complete Analysis

Step-by-step flow for a full analysis:

**Phase 1: Query Submission**
1. User enters query on QueryBuilderPage
2. User optionally pastes source documents
3. User clicks "INITIATE DEEP ANALYSIS"
4. Frontend POSTs to /api/analysis
5. Backend creates analysis_job record (status: 'created')
6. Backend queues background task
7. Frontend redirects to /analysis/{id}
8. Frontend connects to SSE stream

**Phase 2: Ingestion**
1. Background task starts, status → 'ingesting'
2. If source documents provided:
   - Create source record (type: 'paste')
   - Create document record
   - Parse content (extract metadata if possible)
   - Chunk text with overlap
   - Generate embeddings for each chunk
   - Store chunks with embeddings
   - Mark chunks as indexed
3. Emit progress events via SSE
4. Save checkpoint

**Phase 3: Query Expansion**
1. Status → 'expanding'
2. Check query_expansions cache for similar query
3. If not cached:
   - Call LLM to analyze query
   - Call LLM to generate 15-20 variations
   - Cache expansions
4. Emit progress event with expansion count

**Phase 4: Retrieval**
1. Status → 'retrieving'
2. Generate embeddings for all query variations
3. Run parallel vector searches (one per variation)
4. Aggregate results, deduplicate by chunk_id
5. Score chunks by retrieval frequency (found by more queries = higher score)
6. Take top K chunks (K = 50-100)
7. If insufficient results from KB, optionally trigger web search agent
8. Emit progress event with chunk count
9. Save checkpoint

**Phase 5: Extraction**
1. Status → 'extracting'
2. For each retrieved chunk (can parallelize):
   - Run APOR extraction (multi-pass or single-pass based on depth)
   - Extract entities with confidence scores
   - Extract relationships
   - Store raw extractions
   - Emit progress event per chunk
3. Save checkpoint

**Phase 6: Resolution**
1. Status → 'resolving'
2. Load all extracted entities
3. Apply signal amplification (boost entities found multiple times)
4. Group similar entities
5. LLM-confirm merges for ambiguous groups
6. Merge duplicates, combine provenance
7. Mark final entities as resolved
8. Save checkpoint

**Phase 7: Synthesis**
1. Status → 'synthesizing'
2. Build final graph (nodes + edges)
3. Calculate impact scores based on connection count
4. Generate report:
   - Executive summary
   - Key findings
   - APOR sections
   - Methodology note
5. Store report
6. Save final checkpoint
7. Status → 'complete'
8. Emit completion event

**Phase 8: Delivery**
1. Frontend receives 'complete' event
2. Frontend fetches /api/graph/{id}
3. Frontend fetches /api/analysis/{id}/report
4. Frontend renders NetworkGraph with real data
5. User interacts with graph, clicks nodes, reads report

### 7. Configuration & Environment

**Environment Variables:**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dap

# Redis (for caching, optional for MVP)
REDIS_URL=redis://localhost:6379/0

# LLM Gateway
LLM_GATEWAY_URL=http://localhost:8001

# Embedding Service (can use same LLM gateway or direct)
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=...

# LLM Provider (in llm-gateway)
GEMINI_API_KEY=...
# OPENAI_API_KEY=...  # future
# ANTHROPIC_API_KEY=...  # future

# Application
CHUNK_SIZE=2000
CHUNK_OVERLAP=200
MAX_CHUNKS_PER_QUERY=100
QUERY_EXPANSION_COUNT=15
EXTRACTION_PASSES=6  # per chunk for 'deep' mode

# Feature Flags
ENABLE_WEB_SEARCH=false  # Phase 2
ENABLE_HYPOTHESIS=false  # Phase 2
```

**Directory Structure:**

```
dap/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── services/
│   │   ├── agents/
│   │   ├── clients/
│   │   ├── prompts/
│   │   ├── models/
│   │   └── workers/
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
│
├── llm-gateway/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── providers/
│   │   └── middleware/
│   ├── requirements.txt
│   └── pyproject.toml
│
├── docs/
│   ├── architecture.md
│   ├── api-reference.md
│   └── deployment.md
│
├── scripts/
│   ├── setup-local.sh
│   ├── run-dev.sh
│   └── migrate.sh
│
├── Makefile
└── README.md
```

### 8. Implementation Phases

**Phase 1: Foundation (Current — Tasks 1-4)**
- Project structure
- Database schema with pgvector
- Pydantic models
- API stubs

**Phase 2: Core Pipeline (Tasks 5-14)**
- LLM Gateway
- Document ingestion + chunking
- Basic embedding generation
- APOR extraction
- Graph output
- SSE progress

**Phase 3: Knowledge Base (New)**
- Embedding service integration
- Vector search with pgvector
- Query expansion system
- Source management
- Multi-document knowledge base

**Phase 4: Agentic Features (New)**
- Agent base class
- Fallback chains
- Signal amplification
- Retry policies
- Degraded result handling

**Phase 5: Frontend (Task 17 + Query Builder)**
- Query Builder page
- API integration
- Real-time progress
- Graph interaction

**Phase 6: Advanced (Future)**
- Web search agent
- PDF upload + parsing
- Hypothesis generation
- User authentication
- Multi-tenant

### 9. Setup Instructions

**Local Development Setup:**

```bash
# 1. Prerequisites
brew install postgresql@15 python@3.11 node@20

# 2. Start PostgreSQL
brew services start postgresql@15

# 3. Create database with pgvector
psql postgres -c "CREATE DATABASE dap;"
psql dap -c "CREATE EXTENSION vector;"

# 4. Clone and setup backend
cd dap/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
alembic upgrade head

# 5. Setup LLM Gateway
cd ../llm-gateway
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with GEMINI_API_KEY

# 6. Setup Frontend
cd ../frontend
npm install
cp .env.example .env

# 7. Run all services (separate terminals)
# Terminal 1: Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 2: LLM Gateway
cd llm-gateway && source venv/bin/activate && uvicorn app.main:app --reload --port 8001

# Terminal 3: Frontend
cd frontend && npm run dev

# 8. Verify
curl http://localhost:8000/health  # Backend
curl http://localhost:8001/health  # LLM Gateway
open http://localhost:5173         # Frontend
```

### 10. Key Dependencies

**Backend (requirements.txt):**
```
fastapi==0.109.0
uvicorn==0.27.0
sqlalchemy==2.0.25
asyncpg==0.29.0
alembic==1.13.1
pydantic-settings==2.1.0
httpx==0.26.0
python-multipart==0.0.6
pgvector==0.2.4
pypdf==4.0.0
tiktoken==0.5.2
numpy==1.26.3
```

**LLM Gateway (requirements.txt):**
```
fastapi==0.109.0
uvicorn==0.27.0
pydantic-settings==2.1.0
google-generativeai==0.4.0
httpx==0.26.0
tenacity==8.2.3
```

**Frontend (package.json):**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    "d3": "^7.8.5",
    "lucide-react": "^0.300.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/d3": "^7.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

## Summary

This architecture provides:

1. **Simplest vector storage** — pgvector in existing PostgreSQL
2. **Prompt expansion** — LLM-generated query variations for better retrieval
3. **Agentic behavior** — Fallback chains, signal amplification, graceful degradation
4. **Growing knowledge base** — Documents accumulate, every query searches all content
5. **Clean separation** — Frontend / Backend / LLM Gateway as distinct components
6. **Incremental buildability** — Can implement in phases without major refactoring