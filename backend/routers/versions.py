"""
Versions router - handles version CRUD and workflow operations.
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.config import PROJECTS_DIR
from backend.graph import get_compiled_graph, WorkflowState
from backend.storage import ProjectStorage, VersionRecord

logger = logging.getLogger(__name__)
router = APIRouter(tags=["versions"])
storage = ProjectStorage()

# Job executor for running workflow tasks
job_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job-runner")


class VersionSummary(BaseModel):
    version_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    status: str
    quality_score: Optional[float]
    summary: str
    metrics: Dict[str, Any]
    parent_version_id: Optional[str] = None
    progress: int = 0


class VersionDetail(BaseModel):
    version: VersionSummary
    model_ir: Dict[str, Any]
    analysis: Dict[str, Any]
    code: Dict[str, Any]
    tests: Dict[str, Any]
    critique: Optional[Dict[str, Any]]
    plantuml_path: Optional[str]
    model_text: Optional[str] = None
    model_format: Optional[str] = None


class CreateVersionRequest(BaseModel):
    model_text: str = Field(..., description="Raw UML model text")
    model_format: Literal["plantuml", "mermaid", "text"] = Field(
        default="plantuml", description="Model format"
    )
    description: str = Field(default="", description="Description of this version")


class UpdateVersionRequest(BaseModel):
    model_text: str = Field(..., description="Updated UML model text")
    model_format: Literal["plantuml", "mermaid", "text"] = Field(
        default="plantuml", description="Model format"
    )


class WorkflowJobResponse(BaseModel):
    job_id: str
    project_id: str
    status: Literal["queued", "running", "completed", "failed"]
    message: str
    version_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _version_record_to_summary(record: VersionRecord) -> VersionSummary:
    """Convert VersionRecord to VersionSummary."""
    return VersionSummary(
        version_id=record.version_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        status=record.status,
        quality_score=record.quality_score,
        summary=record.summary,
        metrics=record.metrics or {},
        parent_version_id=record.parent_version_id,
        progress=record.progress,
    )


def _version_record_to_detail(record: VersionRecord) -> VersionDetail:
    """Convert VersionRecord to VersionDetail."""
    return VersionDetail(
        version=_version_record_to_summary(record),
        model_ir=record.model_ir or {},
        analysis=record.analysis or {},
        code=record.code or {},
        tests=record.tests or {},
        critique=record.critique,
        plantuml_path=record.plantuml_path,
        model_text=record.model_text,
        model_format=record.model_format,
    )


def _run_workflow_sync(job_id: str, project_id: str, version_id: str, model_text: str, model_format: str, description: str):
    """Run workflow synchronously (for background task)."""
    try:
        logger.info(f"[API] Starting workflow for project {project_id} (job {job_id})")
        try:
            storage.update_job(job_id=job_id, status="running", message="Workflow running")
        except Exception as e:
            logger.warning(f"[API] Unable to update job status for {job_id}: {e}")
        
        # Get project tags for better analysis context
        project_tags = []
        try:
            conn = storage._get_connection()
            cursor = conn.execute("SELECT tags FROM projects WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                project_tags = row[0].split(",")
        except Exception as e:
            logger.warning(f"[API] Unable to fetch project tags: {e}")
        
        graph = get_compiled_graph()
        initial_state = WorkflowState(
            project_id=project_id,
            model_text=model_text,
            model_format=model_format,
            description=description,
            version_id=version_id,
            job_id=job_id,
            project_tags=project_tags,
        )
        
        result = graph.invoke(initial_state)
        version_id = result.get("final_report", {}).get("version_id") or initial_state.version_id
        try:
            storage.update_job(job_id=job_id, status="completed", message="Workflow completed", version_id=version_id)
        except Exception as e:
            logger.warning(f"[API] Unable to update job status for {job_id}: {e}")
        
        logger.info(f"[API] Workflow completed for project {project_id}: {result.get('final_report', {}).get('status')}")
        return result
    except Exception as e:
        logger.error(f"[API] Workflow failed for project {project_id}: {e}", exc_info=True)
        try:
            storage.update_job(job_id=job_id, status="failed", message=str(e))
        except Exception as ex:
            logger.warning(f"[API] Unable to update job failed status for {job_id}: {ex}")
        raise


@router.get("/projects/{project_id}/versions", response_model=List[VersionSummary])
async def list_versions(project_id: str, limit: int = Query(default=50, le=100)):
    """List versions for a project."""
    try:
        versions = storage.list_versions(project_id, limit=limit)
        return [_version_record_to_summary(v) for v in versions]
    except Exception as e:
        logger.error(f"[API] Error listing versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/versions/{version_id}", response_model=VersionDetail)
async def get_version(project_id: str, version_id: str):
    """Get detailed version information."""
    try:
        version = storage.get_version(project_id, version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        
        return _version_record_to_detail(version)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error getting version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/projects/{project_id}/versions/{version_id}", response_model=VersionSummary)
async def update_version_text(project_id: str, version_id: str, request: UpdateVersionRequest):
    """Update the UML text and format for a version."""
    try:
        version = storage.get_version(project_id, version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        
        storage.update_version(
            project_id=project_id,
            version_id=version_id,
            model_text=request.model_text,
            model_format=request.model_format,
        )
        
        updated_version = storage.get_version(project_id, version_id)
        if not updated_version:
            raise HTTPException(status_code=500, detail="Failed to update version")
        
        return _version_record_to_summary(updated_version)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error updating version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/versions/{version_id}/start", response_model=WorkflowJobResponse, status_code=202)
async def start_version_workflow(project_id: str, version_id: str):
    """Start workflow for an existing version. Returns job info."""
    try:
        ver = storage.get_version(project_id, version_id)
        if not ver:
            raise HTTPException(status_code=404, detail="Version not found")
        
        job_id = uuid.uuid4().hex
        storage.create_job(job_id=job_id, project_id=project_id, status="queued", message="Workflow queued")
        
        job_executor.submit(
            _run_workflow_sync,
            job_id,
            project_id,
            version_id,
            ver.model_text or "",
            ver.model_format or "plantuml",
            "",
        )
        
        return WorkflowJobResponse(
            job_id=job_id,
            project_id=project_id,
            status="queued",
            message="Workflow queued for execution",
            version_id=version_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error starting workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/versions", response_model=VersionSummary, status_code=201)
async def create_version(project_id: str, request: CreateVersionRequest):
    """Create a new version and optionally start workflow."""
    try:
        version_id = uuid.uuid4().hex
        
        # Get latest version to set parent
        latest_version = storage.get_latest_version(project_id)
        parent_version_id = latest_version.version_id if latest_version else None
        
        storage.create_version(
            project_id=project_id,
            parent_version_id=parent_version_id,
            status="pending",
            summary=request.description or "New version",
            metrics={},
            model_ir={},
            analysis={},
            code={},
            tests={},
            critique={},
            plantuml_path=None,
            model_text=request.model_text,
            model_format=request.model_format,
            quality_score=None,
            version_id=version_id,
            progress=0,
        )
        
        version = storage.get_version(project_id, version_id)
        if not version:
            raise HTTPException(status_code=500, detail="Failed to create version")
        
        return _version_record_to_summary(version)
    except Exception as e:
        logger.error(f"[API] Error creating version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/versions/{version_id}/plantuml")
async def get_plantuml(project_id: str, version_id: str):
    """Get PlantUML diagram for a version."""
    try:
        version = storage.get_version(project_id, version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        
        if not version.plantuml_path:
            raise HTTPException(status_code=404, detail="PlantUML diagram not available")
        
        from fastapi.responses import FileResponse
        from pathlib import Path
        
        plantuml_file = Path(version.plantuml_path)
        if not plantuml_file.exists():
            raise HTTPException(status_code=404, detail="PlantUML file not found")
        
        return FileResponse(plantuml_file, media_type="text/plain")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error getting PlantUML: {e}")
        raise HTTPException(status_code=500, detail=str(e))
