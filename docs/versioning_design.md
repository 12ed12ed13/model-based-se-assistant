        # Project Memory & Versioning Design (Option B)

## Goals
- Persist every workflow run as a **version** tied to a `project_id`
- Track artifacts (IR, analysis, code, tests, PlantUML, critique) and metadata (quality score, status)
- Compute structural + semantic diffs between versions and recommendation status changes
- Expose REST + UI surfaces for uploading new UML, browsing history, comparing versions, and updating recommendation states

## Storage Architecture
We will introduce a lightweight SQLite store (`projects.db`) managed under `backend/storage.py`. It complements the existing JSON snapshot and keeps artifacts on disk.

### Tables
| Table | Key Columns | Notes |
|-------|-------------|-------|
| `projects` | `project_id (TEXT PRIMARY KEY)` | Friendly name, created_at, description |
| `versions` | `version_id (TEXT PK)`, `project_id (FK)`, `created_at`, `parent_version_id`, `quality_score`, `status` | Stores summary level info; JSON columns for metrics/diffs pointers |
| `artifacts` | `artifact_id`, `version_id`, `kind` (`model_ir`, `analysis`, `code`, `tests`, `plantuml`, `critique`) | Large JSON/text blobs saved to disk, referenced here |
| `recommendations` | `rec_id`, `version_id`, `title`, `priority`, `status` (`open`, `resolved`, `ignored`, `regressed`), `origin_version` | Tracks lifecycle across versions |
| `diffs` | `diff_id`, `project_id`, `from_version`, `to_version`, `diff_json` | Cached diff results to avoid recomputation |

Artifactual files (code/test/plantuml exports) remain under `/projects/{project_id}/{version_id}/...` for auditability.

## Data Flow
1. **Upload UML** → FastAPI endpoint persists raw PlantUML and input metadata
2. **Orchestrator** runs with `previous_version` context (latest or explicit)
3. **Diff Engine** compares `previous.model_ir` vs `current.model_ir`, and prior recommendations vs new findings
4. **Storage Layer** writes new version rows + artifact pointers
5. UI queries `/projects/:id/versions` to render timeline + diffs + recommendation status

## Diff Specification
We'll create `backend/utils/diff.py` with:
- `diff_classes(prev_ir, curr_ir)` → added/removed/changed classes, attributes, methods
- `diff_relationships(prev, curr)` → added/removed edges + multiplicity/type changes
- `diff_metrics(prev_metrics, curr_metrics)` → delta of quality metrics (avg methods/class, LCOM, etc.)
- `diff_recommendations(prev_recs, curr_findings)` → mark resolved (finding disappeared), recurring (same issue/entities), new issues
- `VersionDiff` Pydantic model capturing:
  ```json
  {
    "structure": {"classes_added": [], "classes_removed": [], "classes_modified": []},
    "relationships": {...},
    "metrics_delta": {...},
    "recommendations": {"resolved": [], "regressed": [], "new": []},
    "summary": "3 classes added, SRP issue resolved, DIP regression detected"
  }
  ```

## PlantUML Export Strategy
- Add `backend/exporters/plantuml.py` with `ir_to_plantuml(model_ir) -> str`
- Store exported PlantUML per version (`projects/{id}/{version_id}/model_generated.puml`)
- Provide `/versions/{vid}/plantuml` endpoint returning both original upload and generated version; UI can render via PlantUML server or Mermaid gateway

## API Surface (FastAPI)
| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/projects` | Create project with optional description |
| `GET` | `/projects` | List projects & latest version summary |
| `POST` | `/projects/{project_id}/versions` | Upload UML + description, trigger orchestrator run |
| `GET` | `/projects/{project_id}/versions` | List versions w/ status, metrics, timestamps |
| `GET` | `/projects/{project_id}/versions/{version_id}` | Retrieve artifacts, findings, recommendation statuses |
| `GET` | `/projects/{project_id}/compare?from=...&to=...` | Return diff JSON (structural, semantic, recommendations) |
| `POST` | `/projects/{project_id}/versions/{version_id}/recommendations/{rec_id}` | Update recommendation status & optional note |
| `GET` | `/projects/{project_id}/versions/{version_id}/plantuml` | Download generated PlantUML or PNG |

## UI Notes
React (Vite) SPA served from `/web` build output:
- Project list + search
- Version timeline showing status badges & quality score trend
- Detail view with tabs: Diagram (original vs generated PlantUML), Diffs, Findings & Recommendations (with status chips), Code/Test viewer, Critique log
- Recommendation panel supports status toggles and optional comments; uses websockets or polling for updates.

## Next Steps
1. Implement `storage.py` (SQLite layer + helper methods)
2. Add diff utilities + PlantUML exporter
3. Wire orchestrator to load previous version context and persist new version snapshots
4. Build FastAPI service + React UI scaffolding
5. Add tests + docs
