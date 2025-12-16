"""DAP Backend - FastAPI Application"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, documents, graph, sse

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


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
