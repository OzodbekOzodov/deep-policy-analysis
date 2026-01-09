"""DAP Backend - FastAPI Application"""

from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api import analysis, documents, graph, sse, knowledge, entities
from app.api.deps import get_db

app = FastAPI(
    title="DAP API",
    description="Deep Analysis Platform - APOR Entity Extraction API",
    version="0.1.0"
)

# CORS configuration for frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(analysis.router)
app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(sse.router)
app.include_router(knowledge.router)
app.include_router(entities.router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.

    Verifies API is running and database connection is working.
    """
    database_status = "connected"

    try:
        # Try to execute a simple query to verify DB connection
        await db.execute(text("SELECT 1"))
    except Exception as e:
        database_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "database": database_status
    }
