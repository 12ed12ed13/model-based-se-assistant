"""
Jobs router - handles workflow job status and monitoring.
"""

import logging
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.storage import ProjectStorage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jobs"])
storage = ProjectStorage()


class WorkflowJobResponse(BaseModel):
    job_id: str
    project_id: str
    status: Literal["queued", "running", "completed", "failed"]
    message: str
    version_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get("/projects/{project_id}/jobs", response_model=List[WorkflowJobResponse])
async def list_jobs(project_id: str, limit: int = Query(default=50, le=100)):
    """List recent workflow job statuses for a project."""
    try:
        jobs = storage.list_jobs(project_id, limit=limit)
        return [
            WorkflowJobResponse(
                job_id=j["job_id"],
                project_id=j["project_id"],
                status=j["status"],
                message=j.get("message", ""),
                version_id=j.get("version_id"),
                created_at=datetime.fromisoformat(j["created_at"]) if j.get("created_at") else None,
                updated_at=datetime.fromisoformat(j["updated_at"]) if j.get("updated_at") else None,
            )
            for j in jobs
        ]
    except Exception as e:
        logger.error(f"[API] Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/jobs/{job_id}", response_model=WorkflowJobResponse)
async def get_job(project_id: str, job_id: str):
    """Get a workflow job status."""
    try:
        j = storage.get_job(job_id)
        if not j or j.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return WorkflowJobResponse(
            job_id=j["job_id"],
            project_id=j["project_id"],
            status=j["status"],
            message=j.get("message", ""),
            version_id=j.get("version_id"),
            created_at=datetime.fromisoformat(j["created_at"]) if j.get("created_at") else None,
            updated_at=datetime.fromisoformat(j["updated_at"]) if j.get("updated_at") else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error getting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))
