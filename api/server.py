"""
api/server.py
--------------
FastAPI REST API server for JOSEPH (Phase 2+).

Provides HTTP endpoints so external tools, mobile apps,
or browser extensions can communicate with Joseph.

Phase 1: Basic health check endpoint only.
Phase 2+: Full chat, memory, and automation endpoints.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from configs.settings import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="JOSEPH AI Assistant API",
    description="Local AI assistant API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", f"http://{settings.API_HOST}:{settings.API_PORT}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "assistant": settings.JOSEPH_NAME, "phase": 1}


@app.get("/")
async def root():
    return {"message": f"{settings.JOSEPH_NAME} API is running."}
