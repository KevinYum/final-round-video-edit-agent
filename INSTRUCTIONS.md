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

## v0.5.0 — 2026-03-10T10:30:00Z — Conversational Edit Request Handling

**User Request:**
> Implement chat_edit() or POST /projects/:id/chat. Input: project_id, user_message, conversation_history, optional execution_mode (plan_only/apply). 4 edit categories: trim/cut/delete, reorder/insert/replace, text overlays/titles/subtitles, aspect ratio/crop/reframe. Output: assistant response, structured edit plan (JSON), needs_clarification bool, updated project state. Design version system for revision/recovery. Plan generation only (no real editing execution). Use langchain with openai model for LLM planning.

**Changes Made:**
- Created `backend/models/version.py` — `ProjectVersion` (timeline snapshots) and `ConversationMessage` models
- Added `versions` relationship to `Project` model
- Refactored `backend/schemas.py` → `backend/schemas/` package (project, chat, version modules)
- Created `backend/schemas/chat.py` — `ChatRequest`, `ChatResponse`, `EditPlan`, `ToolStep`
- Created `backend/schemas/version.py` — `VersionOut`, `VersionDetailOut`, `ConversationMessageOut`, `RevertRequest`
- Created `backend/services/tools.py` — 11 edit tool definitions across 4 categories (trim, reorder, text, aspect)
- Created `backend/services/llm.py` — LangChain + ChatOpenAI integration with project-context system prompt, JSON parsing with fallback
- Created `backend/services/chat.py` — Chat orchestrator: loads project, manages versions, calls LLM, stores conversation
- Created `backend/services/version.py` — Version management: list, detail, revert, conversation history
- Created `backend/routers/chat.py` — `POST /{project_id}/chat`
- Created `backend/routers/versions.py` — `GET/POST` version endpoints (list, detail, revert)
- Updated `backend/config.py` — added `OPENAI_API_KEY`, `OPENAI_MODEL`
- Updated `backend/main.py` — registered chat and versions routers, bumped to v0.5.0
- Updated `.env.example` — added OpenAI config
- Added `langchain>=0.3.0`, `langchain-openai>=0.3.0` to dependencies
- Created shared `tests/conftest.py` — unified test DB setup across all test files
- Created `tests/test_tools.py` — 5 tests for tool definitions
- Created `tests/test_chat_api.py` — 8 tests for chat endpoint (plan, apply, clarification, history, errors)
- Created `tests/test_versions_api.py` — 8 tests for version endpoints (list, detail, revert)
- Updated CLAUDE.md — new endpoints, DB tables, conversational edit flow, tool list, version system
- All 44 tests pass

---

## v0.5.1 — 2026-03-10T11:00:00Z — Cleanup: README, Config, Env

**User Request:**
> 1. In README don't draw the full services diagram, just articulate and keep the agent loop part
> 2. It seems you are adding a test main, if no useful remove it
> 3. Only use OpenAI API key, remove Anthropic related API key and logics
> 4. HOST and PORT is specified on running, should not be in .env causing confusion

**Changes Made:**
- Replaced verbose ASCII services diagram in README with concise 4-step text description
- Verified `tests/__init__.py` is empty but required for module resolution (kept)
- Removed Anthropic API key references from `.env` and `.env.example`
- Removed `HOST` and `PORT` from `.env`, `.env.example`, and `backend/config.py`
- All 44 tests pass

---

## v0.5.2 — 2026-03-10T11:15:00Z — Frontend: Chat Dialog UI

**User Request:**
> 1. When edit it should be a dialog box showing all current version's chatting history, not in create job mode
> 2. When entering 1 command it just creates a pending job, the return should be dialog output as well as edit plan if there is no further clarification needed in dialog

**Changes Made:**
- Replaced "Edit with Natural Language" form + "Edit Jobs" list in `frontend/index.html` with chat dialog UI
- Chat dialog includes: message area with scrollable history, text input, execution mode selector (plan_only/apply), send button, version badge
- Updated `frontend/js/app.js`:
  - Removed `loadJobs()` and `/edit` endpoint logic
  - Added `loadChatHistory()` — loads current version's conversation from `GET /versions` endpoints
  - Added `renderChatMessages()` — renders user/assistant bubbles with inline edit plans and clarification indicators
  - Added `renderEditPlan()` — formats tool steps with monospace tool name badges
  - Chat form handler sends to `POST /chat`, appends user bubble immediately, shows "Thinking..." state, then appends assistant response
- Updated `frontend/css/style.css`:
  - Added chat bubble styles (user right-aligned in blue, assistant left-aligned in purple)
  - Added edit plan rendering (green-themed with monospace tool names)
  - Added clarification banner, error bubble, version badge, chat input row styles
  - Removed old job list styles
- All 44 tests pass

---

## v0.6.0 — 2026-03-10T12:00:00Z — Separate Chat/Plan, Strictly Executable Plans, Execute Endpoint

**User Request:**
> 1. Plan only and execute should not be two independent options. After planning gives a good enough plan, I can click an execute button.
> 2. The chat and current plan should be separate — chat in chat, the plan in another box on UI.
> 3. Planning should be strictly JSON structure which will be used in non-LLM tool (MoviePy) call-based execution. Current plan is not executable by a sequential tool call.

**Changes Made:**
- **Schemas** (`backend/schemas/chat.py`):
  - Removed `execution_mode` from `ChatRequest` — chat is always planning
  - Removed `description` from `ToolStep` — steps are now strictly `{step_number, tool_name, params}`
  - Removed `timeline` from `ChatResponse` — chat doesn't return timeline
  - Added `ExecuteResponse(message, version_number, timeline)`
- **LLM prompt** (`backend/services/llm.py`):
  - Updated to require strictly executable params: exact parameter names from tool definitions, concrete values, directly passable as `tool_name(**params)`
- **Chat service** (`backend/services/chat.py`):
  - Removed `execution_mode` parameter — chat never creates versions
- **Execute service** (`backend/services/execute.py`, new):
  - `POST /execute` finds latest ready plan from current version's messages
  - Creates new version with timeline snapshot
  - Returns `ExecuteResponse` with new version number and timeline
  - Actual MoviePy execution deferred to future version
- **Router** (`backend/routers/chat.py`):
  - Updated chat endpoint (removed execution_mode)
  - Added `POST /{project_id}/execute` endpoint
- **Frontend**:
  - Side-by-side layout: Chat (left) + Plan (right) in `.edit-layout` grid
  - Chat only shows conversation text (no inline plans)
  - Plan box shows latest executable plan with tool names + params
  - Execute button on plan box calls `POST /execute`, refreshes timeline
  - Removed execution mode selector
  - Widened main container to 1100px for two-column layout
- **Tests**: Updated all chat/version tests to remove `execution_mode`. Added 4 new execute tests (execute plan, no plan, no version, project not found). Total: 47 tests pass
- Updated CLAUDE.md — new execute endpoint, edit plan structure, frontend layout docs

---

## v0.6.1 — 2026-03-10T13:00:00Z — Plan Validation & Conversation History Improvements

**User Request:**
> Re-assure that LLM receives proper prompt with user request (including history) and all available tool calls, and validate planning result on whether it is a sequence of tool calls with correct input args — if not, the LLM should return needs_clarification.

**Changes Made:**
- **Plan validation** (`backend/services/tools.py`):
  - Added `validate_plan()` function that checks each step against tool definitions
  - Validates: tool_name exists, all required params present, no unknown params
  - Returns list of error strings (empty = valid)
- **Chat service** (`backend/services/chat.py`):
  - After LLM returns a plan, runs `validate_plan()` on it
  - If validation fails: sets `edit_plan=None`, `needs_clarification=True`, appends validation errors to assistant message
  - Imported `validate_plan` from tools service
- **Conversation history** (`backend/services/version.py`):
  - `get_conversation_history()` now includes `edit_plan` and `needs_clarification` in assistant message dicts (not just role/content)
- **LLM context** (`backend/services/llm.py`):
  - `_build_messages()` now reconstructs assistant messages as full JSON (with `assistant_message`, `edit_plan`, `needs_clarification`) so the LLM sees its own prior plans and can iterate
- **Tests**:
  - Added 7 validation tests in `test_tools.py`: valid plan, multi-step, unknown tool, missing required params, unknown params, empty steps, optional params OK
  - Added 2 chat-level validation tests in `test_chat_api.py`: invalid tool name becomes clarification, missing required params becomes clarification
  - Total: 56 tests pass (was 47)
- Updated CLAUDE.md — added Plan Validation and Conversation History sections, updated edit flow steps

---

## v0.6.2 — 2026-03-10T13:30:00Z — Frontend: Show Asset IDs and Clip IDs

**User Request:**
> The frontend asset list should include assetId, or I cannot determine whether the generated plan is what I want to do. Check whether there are other similar issues.

**Changes Made:**
- **Asset table**: Added "Asset ID" column showing first 8 chars of asset UUID in monospace
- **Timeline table**: Replaced `#` column with "Clip ID" column showing full clip ID in monospace
- **CSS**: Added `.id-cell` style (monospace, purple on dark background) for ID display
- Both IDs now visible so users can cross-reference with plan params (`clip_id`, `asset_id`)
- All 56 tests pass

---

## v0.6.3 — 2026-03-10T14:00:00Z — Cumulative Plans & Clean Plan Display

**User Request:**
> The plan doesn't update correctly after I send a second instruction. Also the plan doesn't need to include every LLM response, it just needs to include a structured tool call sequence.

**Changes Made:**
- **LLM prompt** (`backend/services/llm.py`):
  - Added rule: "The edit_plan must be CUMULATIVE: include ALL pending edits from the entire conversation, not just the latest request."
  - LLM now merges new requests with prior plan steps into a single sequential plan
- **Plan box rendering** (`frontend/js/app.js`):
  - Removed narrative summary display (`plan.summary`) from plan box
  - Steps now rendered as function-call style: `tool_name(key=value, key=value)`
  - Param keys highlighted in blue, values in light gray
- **CSS** (`frontend/css/style.css`):
  - Removed `.plan-summary` class
  - Added `.step-param-key` for blue param name highlighting
  - Brightened `.step-params` color for readability
- All 56 tests pass

---

## v0.6.4 — 2026-03-10T14:30:00Z — Explicit Plan Iteration Model

**User Request:**
> It is not a simply accumulate all pending edits, the prompt should include current plan + new user request + available tools to iterate on the plan.

**Changes Made:**
- **Chat orchestrator** (`backend/services/chat.py`):
  - Extracts the latest valid edit plan from conversation history before calling LLM
  - Passes `current_plan` as an explicit parameter to `call_llm()`
- **LLM service** (`backend/services/llm.py`):
  - Added `current_plan` parameter to `call_llm()` and `_build_system_prompt()`
  - Added "### Current Edit Plan" section to system prompt showing the current plan JSON (or "(no plan yet)")
  - Replaced "CUMULATIVE" rule with explicit iteration instructions: "Always start from the Current Edit Plan and iterate on it"
  - LLM now adds/removes/modifies steps on the existing plan rather than reconstructing from scratch
- **Tests** (`tests/test_chat_api.py`):
  - `test_chat_passes_current_plan_to_llm` — verifies second chat passes first plan as `current_plan`
  - `test_chat_no_current_plan_on_first_message` — verifies first chat passes `current_plan=None`
- All 58 tests pass

---
