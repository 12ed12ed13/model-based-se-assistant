"""Persistent storage helpers for project/version history."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.config import PROJECTS_DIR

DB_PATH = PROJECTS_DIR / "projects.db"


def _utcnow() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class VersionRecord:
    project_id: str
    version_id: str
    parent_version_id: Optional[str]
    created_at: str
    status: str
    quality_score: Optional[float]
    summary: Optional[str]
    metrics: Dict[str, Any]
    model_ir: Dict[str, Any]
    analysis: Dict[str, Any]
    code: Dict[str, Any]
    tests: Dict[str, Any]
    critique: Dict[str, Any]
    plantuml_path: Optional[str]
    model_text: Optional[str] = None
    model_format: Optional[str] = None
    progress: int = 0
    updated_at: Optional[str] = None


class ProjectStorage:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def delete_project(self, project_id: str) -> None:
        """Delete a project and all related data (versions, diffs, recommendations, jobs)."""
        with self._connection() as conn:
            # Delete jobs related to the project
            conn.execute("DELETE FROM jobs WHERE project_id = ?", (project_id,))
            # Delete diffs related to the project
            conn.execute("DELETE FROM diffs WHERE project_id = ?", (project_id,))
            # Delete version recommendations and recommendation state for the project's versions
            conn.execute("DELETE FROM version_recommendations WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM recommendation_state WHERE project_id = ?", (project_id,))
            # Delete versions of the project
            conn.execute("DELETE FROM versions WHERE project_id = ?", (project_id,))
            # Finally delete the project itself
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.commit()


    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            cur = conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    tags TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    parent_version_id TEXT,
                    model_text TEXT,
                    model_format TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT,
                    progress INTEGER DEFAULT 0,
                    quality_score REAL,
                    summary TEXT,
                    metrics_json TEXT,
                    model_ir_json TEXT,
                    analysis_json TEXT,
                    code_json TEXT,
                    tests_json TEXT,
                    critique_json TEXT,
                    plantuml_path TEXT,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS recommendation_state (
                    rec_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    latest_version TEXT,
                    status TEXT,
                    note TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS version_recommendations (
                    rec_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    priority TEXT,
                    status TEXT,
                    affected_entities TEXT,
                    design_pattern TEXT,
                    rationale TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(rec_id, version_id)
                );

                CREATE TABLE IF NOT EXISTS diffs (
                    diff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    from_version TEXT NOT NULL,
                    to_version TEXT NOT NULL,
                    diff_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    version_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
            # Ensure new columns exist for versions (schema migration)
            try:
                cur = conn.execute("PRAGMA table_info('versions')")
                cols = [r[1] for r in cur.fetchall()]
                if 'model_text' not in cols:
                    conn.execute("ALTER TABLE versions ADD COLUMN model_text TEXT")
                if 'model_format' not in cols:
                    conn.execute("ALTER TABLE versions ADD COLUMN model_format TEXT")
                if 'progress' not in cols:
                    conn.execute("ALTER TABLE versions ADD COLUMN progress INTEGER DEFAULT 0")
                if 'updated_at' not in cols:
                    conn.execute("ALTER TABLE versions ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
                conn.commit()
            except Exception:
                # If migration fails, continue gracefully; older DB will function without new columns
                pass
            
            # Add tags column to projects if it doesn't exist
            try:
                conn.execute("SELECT tags FROM projects LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE projects ADD COLUMN tags TEXT DEFAULT ''")
                conn.commit()

    # ------------------------------------------------------------------
    # Project helpers
    # ------------------------------------------------------------------
    def ensure_project(self, project_id: str, name: Optional[str] = None, description: str = "", tags: Optional[List[str]] = None) -> None:
        stamp = _utcnow()
        tags_str = ",".join(tags) if tags else ""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (project_id, name, description, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    tags=excluded.tags,
                    updated_at=excluded.updated_at
                """,
                (project_id, name or project_id, description, tags_str, stamp, stamp),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Version helpers
    # ------------------------------------------------------------------
    def create_version(
        self,
        project_id: str,
        parent_version_id: Optional[str],
        status: str,
        summary: str,
        metrics: Dict[str, Any],
        model_ir: Dict[str, Any],
        analysis: Dict[str, Any],
        code: Dict[str, Any],
        tests: Dict[str, Any],
        critique: Dict[str, Any],
        plantuml_path: Optional[str],
        model_text: Optional[str] = None,
        model_format: Optional[str] = None,
        quality_score: Optional[float] = None,
        version_id: Optional[str] = None,
        progress: int = 0,
    ) -> str:
        vid = version_id or uuid.uuid4().hex
        payload = {
            "metrics_json": json.dumps(metrics or {}),
            "model_ir_json": json.dumps(model_ir or {}),
            "analysis_json": json.dumps(analysis or {}),
            "code_json": json.dumps(code or {}),
            "tests_json": json.dumps(tests or {}),
            "critique_json": json.dumps(critique or {}),
        }
        params = {
            "version_id": vid,
            "project_id": project_id,
            "parent_version_id": parent_version_id,
            "model_text": model_text,
            "model_format": model_format,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            "status": status,
            "progress": progress,
            "quality_score": quality_score,
            "summary": summary,
            "plantuml_path": plantuml_path,
            **payload,
        }

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO versions (
                    version_id, project_id, parent_version_id, model_text, model_format, created_at, updated_at, status,
                    progress, quality_score, summary, metrics_json, model_ir_json, analysis_json,
                    code_json, tests_json, critique_json, plantuml_path
                ) VALUES (
                    :version_id, :project_id, :parent_version_id, :model_text, :model_format, :created_at, :updated_at, :status,
                    :progress, :quality_score, :summary, :metrics_json, :model_ir_json, :analysis_json,
                    :code_json, :tests_json, :critique_json, :plantuml_path
                )
                """,
                params,
            )
            conn.commit()
        return vid

    def update_version(
        self,
        project_id: str,
        version_id: str,
        status: Optional[str] = None,
        summary: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        model_ir: Optional[Dict[str, Any]] = None,
        analysis: Optional[Dict[str, Any]] = None,
        code: Optional[Dict[str, Any]] = None,
        tests: Optional[Dict[str, Any]] = None,
        critique: Optional[Dict[str, Any]] = None,
        plantuml_path: Optional[str] = None,
        model_text: Optional[str] = None,
        model_format: Optional[str] = None,
        quality_score: Optional[float] = None,
        progress: Optional[int] = None,
    ) -> None:
        fields = []
        params: List[Any] = []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if summary is not None:
            fields.append("summary = ?")
            params.append(summary)
        if metrics is not None:
            fields.append("metrics_json = ?")
            params.append(json.dumps(metrics or {}))
        if model_ir is not None:
            fields.append("model_ir_json = ?")
            params.append(json.dumps(model_ir or {}))
        if analysis is not None:
            fields.append("analysis_json = ?")
            params.append(json.dumps(analysis or {}))
        if code is not None:
            fields.append("code_json = ?")
            params.append(json.dumps(code or {}))
        if tests is not None:
            fields.append("tests_json = ?")
            params.append(json.dumps(tests or {}))
        if critique is not None:
            fields.append("critique_json = ?")
            params.append(json.dumps(critique or {}))
        if plantuml_path is not None:
            fields.append("plantuml_path = ?")
            params.append(plantuml_path)
        if model_text is not None:
            fields.append("model_text = ?")
            params.append(model_text)
        if model_format is not None:
            fields.append("model_format = ?")
            params.append(model_format)
        if quality_score is not None:
            fields.append("quality_score = ?")
            params.append(quality_score)
        if progress is not None:
            fields.append("progress = ?")
            params.append(progress)

        if not fields:
            # Nothing to update
            return

        params.append(_utcnow())
        params.append(version_id)

        with self._connection() as conn:
            conn.execute(
                f"UPDATE versions SET {', '.join(fields)}, updated_at = ? WHERE version_id = ? AND project_id = ?",
                tuple(params + [project_id]),
            )
            conn.commit()

    def list_versions(self, project_id: str, limit: int = 50) -> List[VersionRecord]:
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT * FROM versions WHERE project_id=? ORDER BY datetime(created_at) DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        return [self._row_to_version(row) for row in rows]

    def get_latest_version(self, project_id: str) -> Optional[VersionRecord]:
        with self._connection() as conn:
            row = conn.execute(
                """SELECT * FROM versions WHERE project_id=? ORDER BY datetime(created_at) DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
        return self._row_to_version(row) if row else None

    def get_version(self, project_id: str, version_id: str) -> Optional[VersionRecord]:
        with self._connection() as conn:
            row = conn.execute(
                """SELECT * FROM versions WHERE project_id=? AND version_id=?""",
                (project_id, version_id),
            ).fetchone()
        return self._row_to_version(row) if row else None

    # ------------------------------------------------------------------
    # Job helpers
    # ------------------------------------------------------------------
    def create_job(self, job_id: str, project_id: str, status: str, message: str = "", version_id: Optional[str] = None) -> None:
        stamp = _utcnow()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (job_id, project_id, status, message, version_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, project_id, status, message, version_id, stamp, stamp),
            )
            conn.commit()

    def update_job(self, job_id: str, status: Optional[str] = None, message: Optional[str] = None, version_id: Optional[str] = None) -> None:
        with self._connection() as conn:
            # Build update statement dynamically
            updates = []
            params = []
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if message is not None:
                updates.append("message = ?")
                params.append(message)
            if version_id is not None:
                updates.append("version_id = ?")
                params.append(version_id)
            if not updates:
                return
            params.append(_utcnow())
            params.append(job_id)
            sql = f"UPDATE jobs SET {', '.join(updates)}, updated_at = ? WHERE job_id = ?"
            conn.execute(sql, tuple(params))
            conn.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return {
            "job_id": row["job_id"],
            "project_id": row["project_id"],
            "status": row["status"],
            "message": row["message"],
            "version_id": row["version_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_jobs(self, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE project_id = ? ORDER BY datetime(created_at) DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [
            {
                "job_id": r["job_id"],
                "project_id": r["project_id"],
                "status": r["status"],
                "message": r["message"],
                "version_id": r["version_id"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def save_diff(self, project_id: str, from_version: str, to_version: str, diff: Dict[str, Any]) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO diffs (project_id, from_version, to_version, diff_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, from_version, to_version, json.dumps(diff or {}), _utcnow()),
            )
            conn.commit()

    def get_diff(self, project_id: str, from_version: str, to_version: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT diff_json FROM diffs
                WHERE project_id=? AND from_version=? AND to_version=?
                ORDER BY datetime(created_at) DESC LIMIT 1
                """,
                (project_id, from_version, to_version),
            ).fetchone()
        return json.loads(row["diff_json"]) if row else None

    def save_recommendations(
        self,
        project_id: str,
        version_id: str,
        recommendations: Iterable[Dict[str, Any]],
        default_status: str = "open",
    ) -> List[str]:
        rec_ids = []
        with self._connection() as conn:
            for rec in recommendations or []:
                rec_id = self._recommendation_id(rec)
                rec_ids.append(rec_id)
                params = (
                    rec_id,
                    project_id,
                    version_id,
                    rec.get("title"),
                    rec.get("description"),
                    rec.get("priority"),
                    rec.get("status", default_status),
                    json.dumps(rec.get("affected_entities", [])),
                    rec.get("design_pattern"),
                    rec.get("rationale"),
                    _utcnow(),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO version_recommendations (
                        rec_id, project_id, version_id, title, description, priority,
                        status, affected_entities, design_pattern, rationale, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
                conn.execute(
                    """
                    INSERT INTO recommendation_state (rec_id, project_id, latest_version, status, note, updated_at)
                    VALUES (?, ?, ?, ?, '', ?)
                    ON CONFLICT(rec_id) DO UPDATE SET
                        project_id=excluded.project_id,
                        latest_version=excluded.latest_version,
                        status=excluded.status,
                        updated_at=excluded.updated_at
                    """,
                    (rec_id, project_id, version_id, rec.get("status", default_status), _utcnow()),
                )
            conn.commit()
        return rec_ids

    def list_recommendations(self, project_id: str, version_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List recommendations for a project, optionally filtered by version_id.
        
        Args:
            project_id: Project identifier
            version_id: Optional version identifier to filter recommendations
            
        Returns:
            List of recommendation dictionaries
        """
        with self._connection() as conn:
            if version_id:
                # Filter by specific version
                rows = conn.execute(
                    """
                    SELECT vr.*, rs.status AS latest_status, rs.latest_version
                    FROM version_recommendations vr
                    LEFT JOIN recommendation_state rs ON rs.rec_id = vr.rec_id
                    WHERE vr.project_id=? AND vr.version_id=?
                    ORDER BY datetime(vr.created_at) DESC
                    """,
                    (project_id, version_id),
                ).fetchall()
            else:
                # Get all recommendations for project
                rows = conn.execute(
                    """
                    SELECT vr.*, rs.status AS latest_status, rs.latest_version
                    FROM version_recommendations vr
                    LEFT JOIN recommendation_state rs ON rs.rec_id = vr.rec_id
                    WHERE vr.project_id=?
                    ORDER BY datetime(vr.created_at) DESC
                    """,
                    (project_id,),
                ).fetchall()
        return [self._row_to_recommendation(row) for row in rows]

    def update_recommendation_status(
        self,
        rec_id: str,
        project_id: str,
        status: str,
        note: str = "",
        version_id: Optional[str] = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO recommendation_state (rec_id, project_id, latest_version, status, note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(rec_id) DO UPDATE SET
                    project_id=excluded.project_id,
                    latest_version=COALESCE(excluded.latest_version, recommendation_state.latest_version),
                    status=excluded.status,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (rec_id, project_id, version_id, status, note, _utcnow()),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _row_to_version(self, row: sqlite3.Row) -> VersionRecord:
        # Get progress safely - check if column exists first
        try:
            progress = row["progress"] if row["progress"] is not None else 0
        except (KeyError, IndexError):
            progress = 0
            
        return VersionRecord(
            project_id=row["project_id"],
            version_id=row["version_id"],
            parent_version_id=row["parent_version_id"],
            created_at=row["created_at"],
            status=row["status"],
            quality_score=row["quality_score"],
            summary=row["summary"],
            metrics=json.loads(row["metrics_json"] or "{}"),
            model_ir=json.loads(row["model_ir_json"] or "{}"),
            analysis=json.loads(row["analysis_json"] or "{}"),
            code=json.loads(row["code_json"] or "{}"),
            tests=json.loads(row["tests_json"] or "{}"),
            critique=json.loads(row["critique_json"] or "{}"),
            plantuml_path=row["plantuml_path"],
            model_text=row["model_text"],
            model_format=row["model_format"],
            progress=progress,
            updated_at=row["updated_at"],
        )

    def _row_to_recommendation(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "rec_id": row["rec_id"],
            "project_id": row["project_id"],
            "version_id": row["version_id"],
            "title": row["title"],
            "description": row["description"],
            "priority": row["priority"],
            "status": row["status"],
            "latest_status": row["latest_status"],
            "affected_entities": json.loads(row["affected_entities"] or "[]"),
            "design_pattern": row["design_pattern"],
            "rationale": row["rationale"],
            "created_at": row["created_at"],
            "latest_version": row["latest_version"],
        }

    def _recommendation_id(self, rec: Dict[str, Any]) -> str:
        from hashlib import sha1

        base = "|".join(
            [
                rec.get("rec_id") or rec.get("id") or "",
                rec.get("title", ""),
                ",".join(sorted(rec.get("affected_entities") or [])),
                rec.get("violated_principle", ""),
            ]
        )
        if base.strip():
            return sha1(base.encode("utf-8")).hexdigest()
        return uuid.uuid4().hex

    def _get_connection(self):
        """Get a database connection (non-context manager version for FastAPI)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
 