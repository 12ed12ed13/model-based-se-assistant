# Comprehensive UI System

A full-stack application for managing UML models, code generation, analysis, and version tracking.

## Architecture

- **Backend**: FastAPI REST API (`backend/api.py`)
- **Frontend**: React + TypeScript + Vite (`ui/`)
- **Storage**: SQLite database for versioning + file-based artifacts
- **Processing**: LangGraph workflow with RAG-enhanced analysis

## Features

### Project Management
- Create and manage multiple projects
- Track project metadata and descriptions
- View project status and quality scores

### Version Control
- Create versions from UML input (PlantUML, Mermaid, text)
- Automatic versioning with parent-child relationships
- Store complete snapshots (IR, analysis, code, tests, PlantUML)

### Diff & Comparison
- Structural diffs (added/removed/changed classes)
- Relationship diffs
- Metrics comparison
- Findings comparison (new vs resolved issues)

### Analysis & Recommendations
- Automated design pattern detection
- SOLID principles validation
- RAG-enhanced analysis with knowledge base
- Prioritized recommendations
- Track recommendation status (open/in-progress/resolved/dismissed)

### Code & Test Generation
- Generate Python code from models
- Generate pytest test suites
- View and download generated artifacts

### Visualization
- PlantUML diagram generation and viewing
- Timeline view of versions
- Quality metrics dashboard

## Installation

### Backend Setup

1. Install Python dependencies:
```bash
cd /Users/rishubbhatia/projects/llm_engineering
source ag/bin/activate
pip install fastapi uvicorn python-multipart
```

2. Start the FastAPI server:
```bash
python -m uvicorn backend.api:app --reload --port 8000
```

The API will be available at http://localhost:8000
API docs at http://localhost:8000/docs

### Frontend Setup

1. Install Node.js dependencies (already done):
```bash
cd ui
npm install
```

2. Start the development server:
```bash
npm run dev
```

The UI will be available at http://localhost:5173

## Usage

### Creating a Project

1. Navigate to http://localhost:5173
2. Click "+ New Project"
3. Enter project details:
   - Project ID (required, unique identifier)
   - Name (optional, human-readable)
   - Description (optional)

### Creating a Version

1. Select a project
2. Click "+ New Version"
3. Paste your UML model (PlantUML, Mermaid, or text)
4. Add a description (optional)
5. Submit

The workflow will run in the background:
- Parse the model
- Analyze for design issues
- Generate code
- Generate tests
- Run tests
- Generate critique
- Save artifacts and persist version

### Viewing Versions

- **Timeline**: Left sidebar shows all versions chronologically
- **Overview Tab**: Quality score, metrics, findings summary
- **Diagram Tab**: View and copy PlantUML source
- **Diff Tab**: Compare with previous version (structural, metrics, findings)
- **Recommendations Tab**: View and update recommendation statuses
- **Code & Tests Tab**: Browse generated source and test files

### Managing Recommendations

1. Navigate to Recommendations tab
2. Click on recommendation title to expand details
3. Use status dropdown to mark as:
   - Open (default)
   - In Progress (actively working on it)
   - Resolved (implemented)
   - Dismissed (won't implement)

## API Endpoints

### Projects
- `GET /projects` - List all projects
- `POST /projects` - Create new project
- `GET /projects/{project_id}` - Get project details

### Versions
- `GET /projects/{project_id}/versions` - List versions
- `GET /projects/{project_id}/versions/{version_id}` - Get version details
- `POST /projects/{project_id}/versions` - Create new version (runs workflow)

### Diffs
- `GET /projects/{project_id}/compare?from={v1}&to={v2}` - Compare versions

### Recommendations
- `GET /projects/{project_id}/recommendations` - List all recommendations
- `GET /projects/{project_id}/versions/{version_id}/recommendations` - List version recommendations
- `POST /projects/{project_id}/recommendations/{rec_id}` - Update recommendation status

### Diagrams
- `GET /projects/{project_id}/versions/{version_id}/plantuml` - Get PlantUML source

## Technology Stack

### Backend
- **FastAPI**: Modern async Python web framework
- **LangGraph**: Agent workflow orchestration
- **LangChain**: LLM integration and RAG
- **SQLite**: Lightweight database for metadata
- **Pydantic**: Data validation and serialization

### Frontend
- **React 18**: UI library
- **TypeScript**: Type-safe JavaScript
- **Vite**: Fast build tool
- **React Router**: Client-side routing
- **TanStack Query**: Server state management
- **Axios**: HTTP client
- **date-fns**: Date formatting

## File Structure

```
backend/
  api.py              # FastAPI REST API
  graph.py            # LangGraph workflow (updated with versioning)
  storage.py          # SQLite storage layer
  utils/
    diff.py           # Version diffing logic
  exporters/
    plantuml.py       # PlantUML generation

ui/
  src/
    api/
      client.ts       # API client and types
    pages/
      ProjectsPage.tsx        # Projects list
      ProjectDetailPage.tsx   # Project detail with routing
    components/
      ProjectList.tsx              # Project cards grid
      CreateProjectModal.tsx       # New project form
      CreateVersionModal.tsx       # New version form
      VersionTimeline.tsx          # Versions sidebar
      VersionDetails.tsx           # Version detail tabs
      DiagramView.tsx              # PlantUML viewer
      DiffView.tsx                 # Diff visualization
      RecommendationsTable.tsx     # Recommendations management
      CodeViewer.tsx               # Code/tests browser
```

## Development

### Running Tests
```bash
# Backend tests
source ag/bin/activate
pytest tests/

# Frontend (add tests later)
cd ui
npm test
```

### Building for Production
```bash
# Frontend
cd ui
npm run build

# Serve with FastAPI
# Update backend/api.py to serve static files from ui/dist
```

## Future Enhancements

- WebSocket for real-time workflow progress
- PlantUML server integration for rendered diagrams
- Export reports as PDF
- Batch operations on recommendations
- Search and filter across projects/versions
- User authentication
- Multi-language code generation (Java, TypeScript, etc.)
