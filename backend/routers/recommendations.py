"""
Recommendations router - handles design recommendations and diffs.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.storage import ProjectStorage
from backend.utils.diff import build_version_diff

logger = logging.getLogger(__name__)
router = APIRouter(tags=["recommendations"])
storage = ProjectStorage()


class RecommendationSummary(BaseModel):
    rec_id: str
    project_id: str
    version_id: str
    title: str
    description: str
    priority: str
    status: str
    affected_entities: List[str]
    design_pattern: Optional[str]
    rationale: Optional[str]
    created_at: datetime


class UpdateRecommendationRequest(BaseModel):
    status: Literal["open", "in_progress", "resolved", "dismissed"] = Field(
        ..., description="New recommendation status"
    )
    note: str = Field(default="", description="Optional note about status change")


class DiffResponse(BaseModel):
    from_version: str
    to_version: str
    summary: str
    structure: Dict[str, Any]
    relationships: Dict[str, Any]
    metrics: Dict[str, Any]
    findings: Dict[str, Any]


@router.get("/projects/{project_id}/recommendations", response_model=List[RecommendationSummary])
async def list_recommendations(project_id: str):
    """List all recommendations for a project."""
    try:
        recs = storage.list_recommendations(project_id)
        return [
            RecommendationSummary(
                rec_id=r["rec_id"],
                project_id=r["project_id"],
                version_id=r["version_id"],
                title=r["title"],
                description=r["description"],
                priority=r["priority"],
                status=r["status"],
                affected_entities=r.get("affected_entities", []),
                design_pattern=r.get("design_pattern"),
                rationale=r.get("rationale"),
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in recs
        ]
    except Exception as e:
        logger.error(f"[API] Error listing recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/versions/{version_id}/recommendations", response_model=List[RecommendationSummary])
async def list_version_recommendations(project_id: str, version_id: str):
    """List recommendations for a specific version."""
    try:
        recs = storage.list_recommendations(project_id, version_id=version_id)
        return [
            RecommendationSummary(
                rec_id=r["rec_id"],
                project_id=r["project_id"],
                version_id=r["version_id"],
                title=r["title"],
                description=r["description"],
                priority=r["priority"],
                status=r["status"],
                affected_entities=r.get("affected_entities", []),
                design_pattern=r.get("design_pattern"),
                rationale=r.get("rationale"),
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in recs
        ]
    except Exception as e:
        logger.error(f"[API] Error listing version recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/recommendations/{rec_id}")
async def update_recommendation(project_id: str, rec_id: str, request: UpdateRecommendationRequest):
    """Update recommendation status."""
    try:
        storage.update_recommendation(
            rec_id=rec_id,
            status=request.status,
            note=request.note,
        )
        return {"status": "success", "rec_id": rec_id}
    except Exception as e:
        logger.error(f"[API] Error updating recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/compare", response_model=DiffResponse)
async def get_diff(project_id: str, from_version: str = None, to_version: str = None):
    """Get diff between two versions."""
    try:
        if not from_version or not to_version:
            raise HTTPException(status_code=400, detail="Both from and to version IDs required")
        
        existing_diff = storage.get_diff(project_id, from_version, to_version)
        if existing_diff:
            return DiffResponse(
                from_version=existing_diff["from_version"],
                to_version=existing_diff["to_version"],
                summary=existing_diff.get("summary", ""),
                structure=existing_diff.get("structure", {}),
                relationships=existing_diff.get("relationships", {}),
                metrics=existing_diff.get("metrics", {}),
                findings=existing_diff.get("findings", {}),
            )
        
        from_ver = storage.get_version(project_id, from_version)
        to_ver = storage.get_version(project_id, to_version)
        
        if not from_ver or not to_ver:
            raise HTTPException(status_code=404, detail="One or both versions not found")
        
        diff = build_version_diff(
            from_ir=from_ver.model_ir or {},
            to_ir=to_ver.model_ir or {},
            from_analysis=from_ver.analysis or {},
            to_analysis=to_ver.analysis or {},
        )
        
        storage.save_diff(project_id, from_version, to_version, diff)
        
        return DiffResponse(
            from_version=from_version,
            to_version=to_version,
            summary=diff.get("summary", ""),
            structure=diff.get("structure", {}),
            relationships=diff.get("relationships", {}),
            metrics=diff.get("metrics", {}),
            findings=diff.get("findings", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error getting diff: {e}")
        raise HTTPException(status_code=500, detail=str(e))
