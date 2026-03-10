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
- **LLM**: LangChain + OpenAI (conversational edit planning)
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
| `POST` | `/api/projects/{project_id}/chat` | Conversational edit (LLM planning) |
| `POST` | `/api/projects/{project_id}/execute` | Execute the current edit plan |
| `GET` | `/api/projects/{project_id}/versions` | List timeline versions |
| `GET` | `/api/projects/{project_id}/versions/{num}` | Get version detail with messages |
| `POST` | `/api/projects/{project_id}/versions/revert` | Revert to a previous version |

### Database Schema (SQLite)
- **projects**: id (string PK), target_aspect_ratio, language, timeline (JSON), transcript (JSON), status, created_at, updated_at
- **assets**: id (UUID string PK), project_id (FK), asset_type, original_filename, file_path, duration_seconds, width, height, format, file_size_bytes, metadata_extra (JSON), created_at
- **project_edit_jobs**: id, project_id (FK), prompt, status, timeline_before (JSON), timeline_after (JSON), error_message, created_at, completed_at
- **project_versions**: id, project_id (FK), version_number, timeline_snapshot (JSON), is_current (bool), created_at
- **conversation_messages**: id, version_id (FK), role, content, edit_plan (JSON), needs_clarification (bool), sequence_number, created_at

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

### Conversational Edit Flow
1. User creates a project with `create_project()`
2. User uploads assets with `load_assets()` — metadata extracted, timeline auto-populated
3. User sends natural language edit via chat dialog → `POST /chat` (planning only)
4. LLM receives project context (timeline, assets, 11 available tools) and conversation history
5. LLM returns: `assistant_message`, `edit_plan` (strictly executable tool steps), `needs_clarification`
6. Plan is validated against tool definitions (tool names, required params, no unknown params)
7. If validation fails or `needs_clarification=true`: plan is rejected, user gets error details or follow-up questions
8. Edit plan displayed in separate plan box on UI with an "Execute" button
9. User reviews plan and clicks Execute → `POST /execute` → new version created with timeline snapshot
10. User can revert to any previous version via `POST /versions/revert`

### Edit Plan Structure (Strictly Executable)
Each plan step is directly executable as `tool_name(**params)`:
```json
{
  "steps": [
    {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "clip-abc", "new_in": 0.0, "new_out": 5.0}}
  ],
  "summary": "Trim first clip to 5 seconds"
}
```
- `params` uses exact parameter names from tool definitions
- Values are concrete (actual clip IDs, asset IDs, numeric values)
- Steps are executed sequentially (MoviePy execution planned for future version)

### Plan Validation
After the LLM returns a plan, `validate_plan()` in `tools.py` checks:
- Each step's `tool_name` exists in the 11 tool definitions
- All required params for that tool are present
- No unknown params are passed

If validation fails, the plan is rejected: `edit_plan` is set to `null`, `needs_clarification` is set to `true`, and the validation errors are appended to the assistant message. This ensures only valid, executable plans reach the Execute button.

### Conversation History (LLM Context)
When calling the LLM, the full conversation history is sent including:
- User messages (plain text)
- Assistant messages reconstructed as JSON with `assistant_message`, `edit_plan`, and `needs_clarification`

This allows the LLM to see its own prior plans and iterate on them based on user feedback.

### Frontend Layout
- Chat and Plan are side-by-side in a two-column layout
- **Chat** (left): conversation history with user/assistant bubbles, text input
- **Plan** (right): current edit plan with tool steps, params, and Execute button
- Plan box updates when LLM returns a ready plan; Execute button creates a new version

### Available Edit Tools (11)
- **Trim/Cut**: `trim_clip`, `split_clip`, `delete_clip`
- **Reorder**: `reorder_clips`, `insert_clip`, `replace_clip`
- **Text**: `add_text_overlay`, `add_title_card`, `add_subtitles`
- **Aspect**: `change_aspect_ratio`, `crop_clip`

### Version System
- Each project has versions (timeline snapshots) created when user executes a plan via `POST /execute`
- Conversation messages are scoped to the current version session
- Reverting restores the project timeline to a previous snapshot
