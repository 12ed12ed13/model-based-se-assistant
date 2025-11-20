"""
FastAPI REST API for Model-Based Software Engineering Assistant.

Exposes endpoints for managing projects, versions, diffs, recommendations,
and provides PlantUML diagram access.
"""

import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import projects, versions, jobs, recommendations

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Model-Based Software Engineering API",
    description="API for managing UML models, code generation, and analysis",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite and CRA defaults
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router)
app.include_router(versions.router)
app.include_router(jobs.router)
app.include_router(recommendations.router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
