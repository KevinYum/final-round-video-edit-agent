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
│   ├── database.py            # SQLite async engine, session factory, path constants
│   ├── schemas.py             # Pydantic request/response models
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py            # Shared DeclarativeBase
│   │   └── project.py         # Project, Asset, ProjectEditJob tables
│   ├── routers/               # API route handlers
│   │   ├── __init__.py
│   │   └── projects.py        # /api/projects/* endpoints
│   └── services/              # Business logic
│       ├── __init__.py
│       ├── metadata.py        # Asset type classification + metadata extraction
│       └── timeline.py        # Timeline creation, mock transcript, auto-populate
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
│   └── test_projects_api.py   # Project API integration tests
│
└── storage/                   # Runtime data (git-ignored)
    ├── .gitkeep
    ├── video_edit_agent.db    # SQLite database (auto-created)
    └── assets/                # Uploaded asset files
        └── {project_id}/      # Per-project asset directories
```

## Agent Loop Design

The video edit agent follows a project-centric create-ingest-edit loop:

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                           │
│  Browser / API ──── Create Project / Upload Assets / Edit       │
└───────┬──────────────────┬────────────────────┬─────────────────┘
        │                  │                    │
        ▼                  ▼                    ▼
┌───────────────┐  ┌───────────────┐  ┌─────────────────────────┐
│ CREATE PROJECT│  │ LOAD ASSETS   │  │ EDIT (NL Command)       │
│               │  │               │  │                         │
│ 1. project_id │  │ 1. Upload     │  │ 1. User types command   │
│ 2. aspect     │  │    files      │  │ 2. Job created with     │
│    ratio      │  │ 2. Classify   │  │    timeline_before      │
│ 3. language   │  │    type       │  │ 3. Agent parses intent  │
│ 4. transcript │  │ 3. Extract    │  │ 4. Maps to FFmpeg ops   │
│    (mocked)   │  │    metadata   │  │ 5. Executes processing  │
│ 5. Empty      │  │ 4. Store file │  │ 6. Timeline updated     │
│    timeline   │  │ 5. Auto-add   │  │ 7. Job → completed      │
│               │  │    to timeline│  │                         │
└───────────────┘  └───────────────┘  └─────────────────────────┘
        │                  │                    │
        └──────────────────┴────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROJECT STATE (SQLite + Filesystem)           │
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │ projects         │    │ Timeline (JSON on project)       │   │
│  │  - id (string)   │    │  ┌─────────────────────────────┐ │   │
│  │  - aspect_ratio  │    │  │ clips: [                    │ │   │
│  │  - language      │──▶ │  │   {asset_id, asset_name,    │ │   │
│  │  - timeline{}    │    │  │    source_in, source_out,    │ │   │
│  │  - transcript{}  │    │  │    timeline_start}           │ │   │
│  └──────────────────┘    │  │ ]                            │ │   │
│         │ 1:N            │  │ total_duration: 25.0         │ │   │
│         ▼                │  └─────────────────────────────┘ │   │
│  ┌──────────────────┐    └──────────────────────────────────┘   │
│  │ assets           │                                           │
│  │  - id (UUID)     │    ┌──────────────────────────────────┐   │
│  │  - type          │    │ storage/assets/{project_id}/     │   │
│  │  - metadata      │───▶│   {asset_id}.mp4                │   │
│  │  - file_path     │    │   {asset_id}.png                │   │
│  └──────────────────┘    └──────────────────────────────────┘   │
│         │ N:1                                                   │
│  ┌──────────────────┐                                           │
│  │ edit_jobs        │    Status: pending → processing           │
│  │  - prompt        │                → completed / failed       │
│  │  - timeline_before│   Each job snapshots timeline state      │
│  │  - timeline_after │                                          │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘

Agent Processing Pipeline (future):
┌──────────┐   ┌───────────┐   ┌──────────┐   ┌──────────────┐
│  Parse   │──▶│  Plan     │──▶│ Execute  │──▶│  Update      │
│  NL Cmd  │   │  FFmpeg   │   │  FFmpeg  │   │  Timeline    │
│          │   │  Ops      │   │  Cmds    │   │  & State     │
└──────────┘   └───────────┘   └──────────┘   └──────────────┘
  "trim 5s"     -ss 5 -i ...    subprocess      timeline{}
                                 .run()          → SQLite
```

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

## Tech Stack

- **Runtime**: Python 3.13+
- **Package Manager**: uv
- **Backend**: FastAPI + Uvicorn
- **Database**: SQLite (aiosqlite + SQLAlchemy async)
- **Frontend**: Vanilla HTML/CSS/JS
- **Metadata**: FFmpeg/ffprobe (optional), Pillow (optional)
- **Video Processing**: FFmpeg (planned)
