# Video Edit Agent - Claude Rules & Specs

## Project Overview
A FastAPI-based video editing agent that allows users to create projects, upload multi-type assets (video, audio, image), and edit them using natural language. Uses SQLite for project/asset management, JSON for timeline/transcript state, and local filesystem for asset storage.

## Tech Stack
- **Backend**: Python + FastAPI
- **Frontend**: Simple HTML/CSS/JS (no framework)
- **Package Manager**: Python uv
- **Database**: SQLite (via aiosqlite + SQLAlchemy async)
- **Media Processing**: MoviePy (metadata extraction, future editing)
- **Image Metadata**: Pillow
- **Config**: python-dotenv (`.env` / `.env.example`)
- **Storage**: Local filesystem (`./storage/assets/{project_id}/`)

## Rules

### R1: Always Test After Changes
After every code change, run the test suite and verify the server starts:
```bash
uv run pytest tests/ -v
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### R2: Update Rules and Specs
When making changes that affect project architecture, conventions, or API contracts, update this CLAUDE.md file and the relevant spec sections accordingly.

### R3: Track All Instructions
Every user request must be logged in `INSTRUCTIONS.md` with:
- Precise timestamp (ISO 8601)
- Incremented version number (vX.Y.Z)
- Summary of the request and changes made

### R4: Code Style
- Use Python type hints everywhere
- Use async/await for all I/O operations
- Keep API endpoints in separate router files
- Use Pydantic models for request/response schemas

### R5: File Organization
- Backend code lives in `backend/`
- Frontend code lives in `frontend/`
- Tests live in `tests/`
- Asset files stored in `storage/assets/{project_id}/`
- SQLite database at `storage/video_edit_agent.db`

### R6: Error Handling
- All API endpoints must return proper HTTP status codes
- Use FastAPI exception handlers for consistent error responses

### R7: Git Hygiene
- Do not commit `storage/assets/*`, `storage/videos/*` (binary files)
- Do not commit `__pycache__/`, `.venv/`, `*.pyc`
- Keep `.gitignore` updated

## Specs

### API Spec

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/projects` | Create a project |
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/projects/{project_id}` | Get project with assets |
| `DELETE` | `/api/projects/{project_id}` | Delete project and all assets |
| `POST` | `/api/projects/{project_id}/assets` | Upload assets (multi-file) |
| `GET` | `/api/projects/{project_id}/assets` | List assets |
| `GET` | `/api/projects/{project_id}/assets/{asset_id}/download` | Download asset |
| `GET` | `/api/projects/{project_id}/timeline` | Get current timeline |
| `POST` | `/api/projects/{project_id}/edit` | Submit NL edit (creates job) |
| `GET` | `/api/projects/{project_id}/jobs` | List edit jobs |

### Database Schema (SQLite)
- **projects**: id (string PK), target_aspect_ratio, language, timeline (JSON), transcript (JSON), status, created_at, updated_at
- **assets**: id (UUID string PK), project_id (FK), asset_type, original_filename, file_path, duration_seconds, width, height, format, file_size_bytes, metadata_extra (JSON), created_at
- **project_edit_jobs**: id, project_id (FK), prompt, status, timeline_before (JSON), timeline_after (JSON), error_message, created_at, completed_at

### Timeline JSON Structure (Clip-Sequence Model)
The timeline represents the final output as an ordered list of clips. Each clip references a source asset with in/out points and a position on the output timeline.
```json
{
  "version": "0.3.0",
  "total_duration": 25.0,
  "clips": [
    {
      "id": "clip-abc12345",
      "asset_id": "uuid-of-source-asset",
      "asset_name": "interview.mp4",
      "asset_type": "video",
      "source_in": 0.0,
      "source_out": 10.0,
      "timeline_start": 0.0,
      "width": 1920,
      "height": 1080,
      "format": "mp4",
      "transcript": {
        "source_asset_id": "uuid-of-transcript-file",
        "start": 0.0,
        "end": 10.0,
        "segments": [
          {"start": 0.5, "end": 3.2, "text": "Welcome to the show"},
          {"start": 3.5, "end": 9.8, "text": "Today we discuss..."}
        ]
      }
    },
    {
      "id": "clip-def67890",
      "asset_id": "uuid-of-another-asset",
      "asset_name": "broll.mp4",
      "asset_type": "video",
      "source_in": 13.0,
      "source_out": 28.0,
      "timeline_start": 10.0,
      "width": 480,
      "height": 270,
      "format": "mp4",
      "transcript": null
    }
  ]
}
```
- `source_in` / `source_out`: which portion of the source asset to use
- `timeline_start`: where this clip begins on the output timeline
- `asset_type`, `width`, `height`, `format`: source asset metadata carried on each clip
- `transcript`: per-clip transcript data (`null` initially, populated during editing/alignment)
  - `source_asset_id`: which transcript file this came from
  - `start` / `end`: time range within the transcript source
  - `segments`: aligned text segments with timestamps
- Subtitles are excluded from clips (they are metadata, not media)
- Project starts with empty timeline and `transcript: null` (no mocked data)

### Agent Loop Design
1. User creates a project with `create_project()`
2. User uploads assets with `load_assets()` — metadata extracted, timeline auto-populated
3. User submits natural language edit command
4. Job is created with `timeline_before` snapshot, status "pending"
5. Worker processes edit (maps NL to FFmpeg ops), updates timeline
6. Job completed with `timeline_after`, project timeline updated
