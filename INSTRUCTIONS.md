# Video Edit Agent - Instruction Log

This file tracks every user request with precise timestamps and version numbers.
It serves as a complete history of how this project was created and evolved.

---

## v0.1.0 — 2026-03-10T8:55:00Z — Project Initialization

**User Request:**
> Initialize this workspace using claude standard with rule and spec.
> 1. Ongoing updates should always update related rules and spec created for claude.
> 2. Always test your code after each prompt, this should be in standard rule.
> 3. All instructions should be saved in a standalone place to track how this project is created and proceed, with precise timestamp and version number appended on each user request.
> 4. This project includes a FastAPI backend and simple web frontend, use python uv as package manager, and can be easily started on localhost for demo purpose.
> 5. This backend is a video edit agent which allows user to upload and edit videos using natural language, the version management of asset (video) can be in local SQLite, and video content can be on the local file system, the API details will be added later.
> 6. Add a README to project, especially it should include (1) text based project file-base hierarchy (2) text based agent loop design.

**Changes Made:**
- Created `CLAUDE.md` with project rules (R1-R7) and specs
- Created `INSTRUCTIONS.md` (this file) for instruction tracking
- Initialized Python uv project with `pyproject.toml`
- Created FastAPI backend structure (`backend/`)
- Created simple web frontend (`frontend/`)
- Set up SQLite models for video version management
- Created `README.md` with file hierarchy and agent loop design
- Added `.gitignore`
- Verified server starts on localhost:8000

---

## v0.2.0 — 2026-03-10T09:16:24Z — Project Management (Video-to-Project Migration)

**User Request:**
> Design and implement first functionality: project management. Implement create_project() and load_assets().
> Input fields: project_id, assets (video/audio/image), target_aspect_ratio, language, transcript.
> System-generated: asset_id, basic metadata, initial timeline, transcript/segment references.
> Change model from video-level to project-level.

**Changes Made:**
- Replaced video-centric models with project-centric architecture
- Created `backend/models/base.py` (shared Base) and `backend/models/project.py` (Project, Asset, ProjectEditJob)
- Deleted `backend/models/video.py` (old Video/VideoVersion/EditJob)
- Rewrote `backend/schemas.py` with CreateProjectRequest, ProjectOut, AssetOut, TimelineOut, etc.
- Created `backend/services/metadata.py` — asset type classification + metadata extraction (ffprobe/Pillow with graceful fallback)
- Created `backend/services/timeline.py` — empty timeline creation, mock transcript, auto-populate timeline on asset upload
- Created `backend/routers/projects.py` — 10 endpoints for project/asset/timeline/edit management
- Deleted `backend/routers/videos.py`
- Updated `backend/database.py` — added ASSET_DIR, removed VIDEO_DIR
- Updated `backend/main.py` — swapped to projects router, version 0.2.0
- Updated frontend (index.html, app.js, style.css) for project workflow: create project → upload assets → view timeline → edit
- Created `tests/test_projects_api.py` — 20 tests covering all endpoints
- Deleted `tests/test_api.py`
- Updated CLAUDE.md specs, README.md, pyproject.toml version bump, .gitignore

---

## v0.2.1 — 2026-03-10T09:24:16Z — Subtitle/Transcript File Upload Support

**User Request:**
> I cannot upload my transcript .txt and .srt files onto the project

**Changes Made:**
- Added `subtitle` asset type classification for `.srt`, `.vtt`, `.ass`, `.sub`, `.ssa`, `.txt` extensions
- Updated frontend file input `accept` attribute to include subtitle/text formats
- Subtitle assets return basic metadata (format only, no duration/dimensions)
- Subtitle assets are excluded from timeline track auto-population (they're metadata, not media)
- Added `.badge-subtitle` CSS style
- Fixed frontend error display for 422 validation errors (`extractError` helper)

---

## v0.3.0 — 2026-03-10T09:30:49Z — Timeline Redesign & Metadata Display

**User Request:**
> 1. you are not showing metadata on webui
> 2. you misunderstand timeline, you should use timeline in video edit syntax, where the final output is a list of timelines like from 0-10s in clips1, 13-20s in clips2, where project contains a lot of uploaded clips

**Changes Made:**
- Redesigned timeline from multi-track model to **clip-sequence model** (proper NLE semantics)
- Timeline structure: `{version: "0.3.0", total_duration, clips: [{id, asset_id, asset_name, source_in, source_out, timeline_start}]}`
- Each clip references a source asset with in/out points and a position on the output timeline
- Updated `backend/services/timeline.py` — `add_assets_to_timeline()` builds ordered clip list with output cursor
- Updated frontend asset table to show Format column with metadata (duration, resolution, file size)
- Updated frontend timeline view to render clip sequence table (source clip, source in/out, timeline position, duration)
- Added `formatTime()` helper for human-readable time display
- Added test for subtitle exclusion from timeline (`test_timeline_subtitle_excluded`)
- Updated CLAUDE.md timeline JSON structure, README.md timeline diagram
- All 22 tests pass

---

## v0.3.1 — 2026-03-10T09:42:36Z — Test DB Isolation Fix

**User Request:**
> it seems you db and persistence having problem, every time I restart the server there is no project, but I can see files under storage

**Changes Made:**
- Root cause: tests imported the production engine and `drop_all` on teardown wiped real DB
- Fixed tests to use isolated in-memory SQLite (`sqlite+aiosqlite://`) with `app.dependency_overrides[get_db]`
- Production DB is never touched by tests now

---

## v0.4.0 — 2026-03-10T09:42:36Z — Env Config & MoviePy Metadata

**User Request:**
> 1. you should use .env and .env-example to configure configs like test/prod, and there will be apikey related env in the future
> 2. I see the duration and resolution for clip are not correctly populated, do you need related sdk to evaluate that? maybe you can add moviePy if it can help you finish that, I may use moviepy later for its edit related apis

**Changes Made:**
- Created `.env.example` and `.env` with config for ENV, STORAGE_DIR, HOST, PORT, future API key placeholders
- Created `backend/config.py` — loads `.env` via python-dotenv, exports ENV, STORAGE_DIR, HOST, PORT
- Updated `backend/database.py` to use config module instead of raw `os.getenv`
- Added `.env` to `.gitignore`
- Added `moviepy>=2.0.0` and `python-dotenv>=1.0.0` to dependencies
- Rewrote `backend/services/metadata.py` to use MoviePy for video/audio metadata extraction:
  - Video: duration, width, height, fps via `VideoFileClip`
  - Audio: duration, channels, sample rate via `AudioFileClip`
  - Image: width, height, format, mode via Pillow (unchanged)
  - Graceful fallback to extension-only if extraction fails
- Bumped version to 0.4.0
- All 22 tests pass

---

## v0.4.1 — 2026-03-10T09:45:19Z — Clip Metadata & Remove Mock Transcript

**User Request:**
> I still don't see the metadata field -- I mean the output video's metadata including duration, resolution, type etc. those can be predefined, and I see you are mocking timeline in initialize that's not necessary, we can start with empty timeline and during the edit the timeline should reflect the real state

**Changes Made:**
- Added `asset_type`, `width`, `height`, `format` fields to each timeline clip so output state is self-contained
- Updated `add_assets_to_timeline()` to pass metadata from asset into clip dict
- Updated router to pass width/height/format in timeline entries
- Updated frontend timeline table to show Type (badge) and Resolution columns
- Removed `generate_mock_transcript()` from project creation — `transcript` starts as `null` unless user provides one
- Updated tests to expect `transcript: null` on project creation
- All 22 tests pass

---

## v0.4.2 — 2026-03-10T09:50:32Z — Per-Clip Transcript Field

**User Request:**
> in the timeline there should be a field for transcript, each clip in timeline should have a transcript source and start timestamp, though it can be populated as None for initial state even if there are transcript files

**Changes Made:**
- Added `transcript` field to each timeline clip (initialized as `null`)
- When populated (during editing/alignment), structure is: `{source_asset_id, start, end, segments: [{start, end, text}]}`
- Updated frontend timeline table to show Transcript column (segment count or "none")
- Removed unused `generate_mock_transcript()` function from timeline service
- Updated CLAUDE.md timeline spec with transcript field documentation
- All 22 tests pass

---
