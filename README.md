# Video Edit Agent

A FastAPI-based video editing agent that allows users to create projects, upload multi-type assets (video, audio, image), and edit them using natural language. Built with Python, SQLite for project/asset management, and local filesystem for asset storage.

## Quick Start

```bash
# Install dependencies
uv sync

# Run the server
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Open in browser
open http://localhost:8000

# Run tests
uv run pytest tests/ -v
```

## Project File Hierarchy

```
video-edit-agent/
├── CLAUDE.md                  # Claude rules, specs, and conventions
├── INSTRUCTIONS.md            # Chronological instruction log (versioned)
├── README.md                  # This file
├── pyproject.toml             # Python project config (uv)
├── .gitignore
│
├── backend/                   # FastAPI backend
│   ├── __init__.py
│   ├── main.py                # App entrypoint, lifespan, mounts
│   ├── config.py              # Environment config (.env loading)
│   ├── database.py            # SQLite async engine, session factory, path constants
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py            # Shared DeclarativeBase
│   │   ├── project.py         # Project, Asset, ProjectEditJob tables
│   │   └── version.py         # ProjectVersion, ConversationMessage tables
│   ├── schemas/               # Pydantic request/response models
│   │   ├── __init__.py        # Re-exports all schemas
│   │   ├── project.py         # Project, Asset, Timeline, EditJob schemas
│   │   ├── chat.py            # ChatRequest, ChatResponse, EditPlan, ToolStep
│   │   └── version.py         # VersionOut, VersionDetailOut, RevertRequest
│   ├── routers/               # API route handlers
│   │   ├── __init__.py
│   │   ├── projects.py        # /api/projects/* endpoints
│   │   ├── chat.py            # /api/projects/{id}/chat endpoint
│   │   └── versions.py        # /api/projects/{id}/versions/* endpoints
│   └── services/              # Business logic
│       ├── __init__.py
│       ├── metadata.py        # Asset type classification + MoviePy metadata extraction
│       ├── timeline.py        # Timeline creation, auto-populate clips
│       ├── tools.py           # 11 edit tool definitions (descriptors)
│       ├── llm.py             # LangChain + OpenAI LLM integration
│       ├── chat.py            # Chat orchestrator service
│       ├── execute.py         # Execute service (apply edit plan, create version)
│       └── version.py         # Version management (list, detail, revert)
│
├── frontend/                  # Simple web UI (static files)
│   ├── index.html             # Main page (project workflow)
│   ├── css/
│   │   └── style.css          # Styles
│   └── js/
│       └── app.js             # Client-side logic
│
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py            # Shared test DB setup (in-memory SQLite)
│   ├── test_projects_api.py   # Project API integration tests (23 tests)
│   ├── test_chat_api.py       # Chat + execute endpoint tests with mocked LLM (13 tests)
│   ├── test_versions_api.py   # Version endpoint tests (8 tests)
│   └── test_tools.py          # Tool definition + validation tests (12 tests)
│
└── storage/                   # Runtime data (git-ignored)
    ├── .gitkeep
    ├── video_edit_agent.db    # SQLite database (auto-created)
    └── assets/                # Uploaded asset files
        └── {project_id}/      # Per-project asset directories
```

## Agent Loop Design

The agent follows a create → ingest → chat loop:

1. **Create Project** — User provides project_id, aspect ratio, language. An empty timeline is initialized.
2. **Load Assets** — Upload video/audio/image files. Each asset is classified, metadata extracted (MoviePy/Pillow), and a clip is appended to the timeline with source in/out points.
3. **Conversational Edit** — User sends natural language edit requests via `POST /chat`. The LLM (OpenAI via LangChain) receives the full project context (timeline, assets, 11 available edit tools) and returns a structured edit plan with exact tool parameters, or asks clarifying questions if the request is ambiguous.
4. **Execute Plan** — When the user is satisfied with the plan, clicking Execute (`POST /execute`) creates a new version with a timeline snapshot. Actual tool execution (MoviePy calls) will be added in a future version.
5. **Version Management** — Users can list versions, inspect conversation history per version, and revert to any previous version.

Edit tools span 4 categories: trim/cut/delete, reorder/insert/replace, text overlays/titles/subtitles, and aspect ratio/crop/reframe. Currently plan generation only — tool execution is planned for a future version.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/projects` | Create a project |
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/projects/{id}` | Get project with assets |
| `DELETE` | `/api/projects/{id}` | Delete project and assets |
| `POST` | `/api/projects/{id}/assets` | Upload assets (multi-file) |
| `GET` | `/api/projects/{id}/assets` | List project assets |
| `GET` | `/api/projects/{id}/assets/{aid}/download` | Download asset file |
| `GET` | `/api/projects/{id}/timeline` | Get current timeline |
| `POST` | `/api/projects/{id}/edit` | Submit NL edit command |
| `GET` | `/api/projects/{id}/jobs` | List edit jobs |
| `POST` | `/api/projects/{id}/chat` | Conversational edit (LLM planning) |
| `POST` | `/api/projects/{id}/execute` | Execute the current edit plan |
| `GET` | `/api/projects/{id}/versions` | List timeline versions |
| `GET` | `/api/projects/{id}/versions/{num}` | Get version detail with messages |
| `POST` | `/api/projects/{id}/versions/revert` | Revert to previous version |

## Tech Stack

- **Runtime**: Python 3.13+
- **Package Manager**: uv
- **Backend**: FastAPI + Uvicorn
- **Database**: SQLite (aiosqlite + SQLAlchemy async)
- **Frontend**: Vanilla HTML/CSS/JS
- **Metadata**: MoviePy, Pillow
- **LLM**: LangChain + OpenAI (conversational edit planning)
- **Video Processing**: MoviePy (planned execution)
