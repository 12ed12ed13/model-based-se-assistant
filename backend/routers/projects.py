"""
Projects router - handles project CRUD operations.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.storage import ProjectStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])
storage = ProjectStorage()


class CreateProjectRequest(BaseModel):
    project_id: str = Field(..., description="Unique project identifier")
    name: Optional[str] = Field(None, description="Human-readable project name")
    description: str = Field(default="", description="Project description")
    tags: List[str] = Field(default_factory=list, description="Technology tags (e.g., 'FastAPI', 'React', 'LangGraph')")


class ProjectSummary(BaseModel):
    project_id: str
    name: Optional[str]
    description: str
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    latest_version_id: Optional[str] = None
    latest_status: Optional[str] = None
    latest_quality_score: Optional[float] = None


@router.post("", response_model=ProjectSummary, status_code=201)
async def create_project(request: CreateProjectRequest):
    """Create a new project."""
    try:
        storage.ensure_project(
            project_id=request.project_id,
            name=request.name,
            description=request.description,
            tags=request.tags,
        )
        
        conn = storage._get_connection()
        cursor = conn.execute(
            "SELECT project_id, name, description, tags, created_at, updated_at FROM projects WHERE project_id = ?",
            (request.project_id,),
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create project")
        
        latest = storage.get_latest_version(request.project_id)
        
        return ProjectSummary(
            project_id=row[0],
            name=row[1],
            description=row[2],
            tags=row[3].split(",") if row[3] else [],
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
            latest_version_id=latest.version_id if latest else None,
            latest_status=latest.status if latest else None,
            latest_quality_score=latest.quality_score if latest else None,
        )
    except Exception as e:
        logger.error(f"[API] Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ProjectSummary])
async def list_projects():
    """List all projects with their latest version summary."""
    try:
        conn = storage._get_connection()
        cursor = conn.execute(
            "SELECT project_id, name, description, tags, created_at, updated_at FROM projects ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()
        
        projects = []
        for row in rows:
            project_id = row[0]
            latest = storage.get_latest_version(project_id)
            
            projects.append(
                ProjectSummary(
                    project_id=row[0],
                    name=row[1],
                    description=row[2],
                    tags=row[3].split(",") if row[3] else [],
                    created_at=datetime.fromisoformat(row[4]),
                    updated_at=datetime.fromisoformat(row[5]),
                    latest_version_id=latest.version_id if latest else None,
                    latest_status=latest.status if latest else None,
                    latest_quality_score=latest.quality_score if latest else None,
                )
            )
        
        conn.close()
        return projects
    except Exception as e:
        logger.error(f"[API] Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}", response_model=ProjectSummary)
async def delete_project(project_id: str):
    """Delete a project and its related data."""
    try:
        conn = storage._get_connection()
        cursor = conn.execute(
            "SELECT project_id FROM projects WHERE project_id = ?",
            (project_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        
        storage.delete_project(project_id)
        return ProjectSummary(
            project_id=project_id,
            name=None,
            description="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"[API] Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}", response_model=ProjectSummary)
async def get_project(project_id: str):
    """Get project details."""
    try:
        conn = storage._get_connection()
        cursor = conn.execute(
            "SELECT project_id, name, description, tags, created_at, updated_at FROM projects WHERE project_id = ?",
            (project_id,),
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        
        latest = storage.get_latest_version(project_id)
        
        return ProjectSummary(
            project_id=row[0],
            name=row[1],
            description=row[2],
            tags=row[3].split(",") if row[3] else [],
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
            latest_version_id=latest.version_id if latest else None,
            latest_status=latest.status if latest else None,
            latest_quality_score=latest.quality_score if latest else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error getting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))
