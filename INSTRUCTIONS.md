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

## v0.7.0 — 2026-03-10T15:00:00Z — Execute Edit Plans with Tool Functions

**User Request:**
> Implement the execution of the previously generated plan. After execute the plan, steps are executed one by one sequentially by making related function calls. Progress should show on UI using "check" and "pending" for current executing step. If execution fails on some step, version cannot be bumped and error msg should be shown. If execution succeeds, version is bumped, chat history is cleared, and timeline is updated to reflect all changes.

**Changes Made:**
- Created `backend/services/tool_executors.py` — 11 tool executor functions (`trim_clip`, `split_clip`, `delete_clip`, `reorder_clips`, `insert_clip`, `replace_clip`, `add_text_overlay`, `add_title_card`, `add_subtitles`, `change_aspect_ratio`, `crop_clip`) + `ToolExecutionError`, `ToolContext`, helper functions (`_find_clip`, `_find_clip_index`, `_find_asset`, `recompute_timeline`), and `TOOL_REGISTRY` mapping
- Modified `backend/schemas/chat.py` — added `StepResult` model (step_number, tool_name, status, error), expanded `ExecuteResponse` with `step_results` list and `success` bool
- Modified `backend/schemas/__init__.py` — exported `StepResult`
- Rewrote `backend/services/execute.py` — real step-by-step execution loop: deep-copies timeline, runs each step via `TOOL_REGISTRY`, records per-step `StepResult`, on failure returns `success=False` without version bump, on success recomputes timeline and creates new version
- Modified `frontend/js/app.js` — `renderPlanBox()` adds step status spans, `executePlan()` shows pending/check/fail per step, updates timeline and version badge on success, shows error on failure
- Modified `frontend/css/style.css` — added `.step-status`, `.step-pending`, `.step-completed`, `.step-failed` classes
- Created `tests/test_tool_executors.py` — 27 unit tests for all 11 executors + `recompute_timeline`
- Updated `tests/test_chat_api.py` — `test_execute_plan` verifies `step_results` and `success`, added `test_execute_step_failure` and `test_execute_updates_project_timeline`
- Updated `tests/test_versions_api.py` — fixed tests to use real clip IDs from uploaded assets
- All 89 tests pass

---

## v0.7.1 — 2026-03-10T16:00:00Z — Plan Persistence & Sequential Video Preview Player

**User Request:**
> 1. As v1 plan is executed, plan box should still linger on v1 with all steps checked, not directly showing empty, until v2's first plan try
> 2. There should be a player box for last generated version's video — preview should be final view, not just clip

**Changes Made:**
- **Plan box persistence** (`frontend/js/app.js`):
  - After successful execution, chat is cleared manually instead of calling `loadChatHistory()` which would reset the plan box
  - Plan box stays visible with all steps checked + "Plan executed" banner until user generates a new plan via chat
- **Sequential video preview player** (`frontend/js/app.js`):
  - Replaced single-clip player with timeline-aware sequential player
  - `player` state object tracks clips list, current index, total duration
  - `renderVideoPreview()` builds clip segment bar showing all video clips proportional to their duration
  - `playerAdvance()` auto-plays next clip when current clip ends (via `ended` event + media fragments `#t=in,out`)
  - `playerJumpTo(index)` + `playerLoadClip()` for clicking clip segments to jump
  - Shows "Clip N/M: name" label and source range, with total duration
- **Player CSS** (`frontend/css/style.css`):
  - Added `.player-clip-bar` (flex bar), `.player-seg` (clip segments with proportional widths), `.seg-label`, `.seg-active` styles
  - Removed old `.clip-selector`, `.clip-btn`, `.download-btn` styles
- **HTML** (`frontend/index.html`): Preview section already in place (unchanged)
- All 89 tests pass

---

## v0.7.2 — 2026-03-10T16:30:00Z — Video Export (MoviePy Rendering)

**User Request:**
> Add an export button in preview section to download the full video of current version.

**Changes Made:**
- Created `backend/services/render.py` — `render_timeline_to_file()`: loads video clips via MoviePy, subclips to source_in/source_out, concatenates, writes to mp4 (libx264 + aac)
- Added `GET /api/projects/{project_id}/export` endpoint in `backend/routers/projects.py`:
  - Builds asset_id → file_path mapping from DB
  - Renders via `asyncio.to_thread()` to avoid blocking the event loop
  - Caches rendered files at `storage/exports/{project_id}/v{N}.mp4`
  - Returns `FileResponse` with `video/mp4` media type
- Added "Export" button in frontend preview player info bar (`frontend/js/app.js`):
  - `exportVideo()` fetches the export endpoint, creates blob download
  - Shows "Rendering..." state while processing
- Added `.export-btn` CSS styles (`frontend/css/style.css`)
- Added `storage/exports/*` to `.gitignore`
- Updated CLAUDE.md API spec table with export endpoint
- All 89 tests pass

---

## v0.8.0 — 2026-03-10T17:00:00Z — Version Semantics Fix & Rendered Preview

**User Request:**
> 1. When executing add_text_overlay, the preview doesn't really change, debug and fix.
> 2. The version is a little errorness — when chat shows v3, executed plan/exported videos should be on v2 (v3 is ongoing), but current logic puts it in v2.

**Follow-up:**
> Use rendered output for each plan execution saved in local storage instead of DOM overlays. Export doesn't need to re-render; rendering happens during plan execution.

**Changes Made:**
- **Version semantics overhaul** (`backend/services/execute.py`, `backend/services/version.py`):
  - Execute no longer creates a new version — updates current version's `timeline_snapshot` and sets `executed=True`
  - New version created lazily on next chat via `ensure_version()` (detects `executed=True` on current version)
  - Version number stays stable during execution (v2 plan → v2 execute → v3 starts on next chat)
- **`executed` flag** (`backend/models/version.py`):
  - Added `executed: bool` column to `ProjectVersion` model (default `False`)
- **Schema update** (`backend/schemas/version.py`):
  - Added `executed: bool = False` to `VersionOut`
- **Router fix** (`backend/routers/versions.py`):
  - Added `executed=v.executed` to all three `VersionOut` constructions (list, detail, revert)
- **Rendered preview during execution** (`backend/services/execute.py`):
  - After successful execution, renders video via `asyncio.to_thread(render_timeline_to_file, ...)`
  - Cached at `storage/exports/{project_id}/v{N}.mp4`
  - Non-fatal: render failure doesn't break execution
- **Frontend preview** (`frontend/js/app.js`):
  - Removed DOM overlay approach (rejected as error-prone)
  - Added `renderExportPreview()` — shows rendered video from `/export` endpoint after execution
  - Added `renderPlanBoxExecuted()` — shows plan with all steps checked when loading executed version
  - `executePlan()` shows "Executing & Rendering..." during process
  - `loadChatHistory()` detects executed version: shows empty chat + executed plan + export preview
- **Test updates** (`tests/test_chat_api.py`, `tests/test_versions_api.py`):
  - Updated assertions for new version semantics: execute stays at same version, `executed=True`
  - `test_revert_to_version` creates v2 via chat after v1 execution
- All 89 tests pass

---

## v0.8.1 — 2026-03-10T17:30:00Z — Render Pipeline: Overlays, Title Cards, Resolution Fix

**User Request:**
> 1. No overlay is created after executing add_text_overlay — only subtitle added
> 2. Second clip renders as tiled/repeated images — source clip only has one earth
> Check whether tool executors are consistent with the plan shown

**Root Cause:**
- `render.py` only did basic `subclip` + `concatenate` — it completely ignored `overlays`, `crop`, `title_card` fields added by tool executors
- Clips with different resolutions caused tiling artifacts when concatenated without normalization

**Changes Made:**
- **Rewrote `backend/services/render.py`** — full rendering pipeline:
  - **Resolution normalization**: determines target size from first video clip, resizes all subsequent clips to match (fixes tiling)
  - **Text overlays**: renders `overlays` list on each clip using MoviePy `TextClip` + `CompositeVideoClip`
  - **Title cards**: renders `title_card` type clips using `ColorClip` + `TextClip`
  - **Crop**: applies MoviePy `cropped()` then resizes back to target
  - **Position mapping**: converts overlay position names (center, top, bottom-left, etc.) to pixel coordinates with margins
  - **Font discovery**: searches common system font paths (macOS Helvetica, Linux DejaVu/Liberation)
  - **Graceful fallback**: overlay/title card failures are non-fatal (logged as warnings, clip still renders)
  - Uses `concatenate_videoclips(method="compose")` for safe multi-resolution concatenation
- Cleared cached exports to force re-render with new pipeline
- All 89 tests pass

---

## v0.8.2 — 2026-03-10T18:00:00Z — Cache-Busting Fix & Subtitle Burn-In

**User Request:**
> 1. When removing one clip from two clips, the rendered output starts empty until page refresh
> 2. Subtitle seems not correctly rendered — must fix

**Changes Made:**
- **Browser cache fix** (`frontend/js/app.js`):
  - Added `?t=${Date.now()}` cache-busting parameter to export URL in `renderExportPreview()`
  - Fixed ordering: `currentVersionNumber` set BEFORE `renderExportPreview()` (was after, causing wrong version label)
- **Subtitle burn-in** (`backend/services/render.py`):
  - Added `_parse_srt_time()` — parses SRT timestamp `00:01:23,456` to seconds
  - Added `_parse_subtitle_file()` — parses SRT/VTT files into `{start, end, text}` dicts (handles WEBVTT header, HTML tag stripping)
  - Added `_make_subtitle_overlays()` — creates TextClip overlays from subtitle file, converts absolute times to clip-relative, clamps to boundaries
  - Integrated subtitle rendering into main render loop (after text overlays, before CompositeVideoClip)
- All 89 tests pass

---

## v0.9.0 — 2026-03-10T18:30:00Z — Per-Step Execution Animation & Version-Isolated Clip IDs

**User Request:**
> 1. Pending marks are 'checked' all at once — do it per-step with animation, add a render_video step in plan box
> 2. After adding transcript, plan executed but clips don't change — propose new clip IDs per version for rollback support

**Changes Made:**
- **Per-step animation** (`frontend/js/app.js`):
  - Added `sleep(ms)` helper function
  - `renderPlanBox()` and `renderPlanBoxExecuted()` now include a `render_video` step (separated visually from tool steps)
  - `executePlan()` iterates `step_results` with 300ms delay between each step's status update (pending -> completed/failed)
  - Render step animates to completed after all tool steps finish
  - On failure, render step also shown as failed
- **Render step CSS** (`frontend/css/style.css`):
  - Added `.step-render-item` with top border separator and margin
- **Version-isolated clip IDs** (`backend/services/execute.py`):
  - After `recompute_timeline()`, regenerates all clip IDs as `clip-{uuid4_hex[:8]}` for version isolation
  - Each executed version gets brand new clip objects, supporting future rollback features
- Version bump to v0.9.0
- All 89 tests pass

---

## v1.0.0 — 2026-03-10T19:00:00Z — Project-wise Version Rollback

**User Request:**
> Let's do next api, which is project wise rollback version: it shows a button, when click it will first prompt a second confirmation, if confirmed, all timeline preview plan chat history should come back to last version. If anything that should be versioned is not currently versioned you can redesign the model. Special case is version 0 cannot further rollback.

**Changes Made:**
- **Version 0 creation** (`backend/services/version.py`):
  - `ensure_version()` now creates v0 (initial timeline snapshot, `executed=True`) alongside v1 on first chat
  - v0 serves as the rollback target when undoing the first edit
- **Rollback service** (`backend/services/version.py`):
  - Added `rollback(project_id, db)` — finds current version N, deletes versions > N-1 (cascade deletes messages), restores target version N-1 as current
  - Raises `ValueError` if at v0 or no versions exist
- **Rollback endpoint** (`backend/routers/versions.py`):
  - Added `POST /api/projects/{project_id}/rollback` — no request body needed
  - Returns `RollbackResponse(message, version_number, timeline)`
  - 400 on v0 rollback attempt, 404 on project not found
  - Cleans up stale export caches for deleted versions
- **Schema** (`backend/schemas/version.py`):
  - Added `RollbackResponse` model
- **Frontend** (`frontend/js/app.js`):
  - Added rollback button next to version badge (orange/amber styling)
  - `rollbackVersion()` shows `confirm()` dialog, calls `POST /rollback`, reloads timeline/preview/chat/plan
  - Button disabled at v0, hidden when no versions
- **CSS** (`frontend/css/style.css`):
  - Added `.rollback-btn` styles (amber theme, disabled state)
- **Tests** (`tests/test_versions_api.py`):
  - Added 5 rollback tests: v1→v0, v0 returns 400, deletes later versions, no versions, project not found
  - Updated existing version count assertions for v0 creation (1→2, 2→3)
- **Tests** (`tests/test_chat_api.py`):
  - Updated version count assertions for v0 creation
- Updated CLAUDE.md — added rollback endpoint to API spec, updated version system docs
- Version bump to v1.0.0

---

## v1.1.0 — 2026-03-10T12:00:00Z — Global Metrics Dashboard

**User Request:**
> Expose or print metrics: total_projects, total_edit_requests, successful_edit_requests, avg_agent_latency_ms, clarification_count, export_count, undo_or_recovery_count. In frontend add those in the bottom. Adding them to database. Adding hooks to update them.

**Changes Made:**
- **Model** (`backend/models/metrics.py`): New `GlobalMetrics` singleton model with counter columns + cumulative latency tracking
- **Schema** (`backend/schemas/metrics.py`): `MetricsOut` response model (avg_agent_latency_ms computed on read)
- **Service** (`backend/services/metrics.py`): `increment()`, `record_latency()`, `get_metrics()` helpers
- **Router** (`backend/routers/metrics.py`): `GET /api/metrics` endpoint
- **Hooks** added at 7 locations:
  - `backend/routers/projects.py` — total_projects (create), export_count (export)
  - `backend/services/llm.py` — LLM call latency measurement (time.monotonic)
  - `backend/services/chat.py` — total_edit_requests, clarification_count, latency recording
  - `backend/services/execute.py` — successful_edit_requests
  - `backend/routers/versions.py` — undo_or_recovery_count (revert + rollback)
- **Frontend** (`frontend/index.html`): Added `<footer id="metrics-bar">` with 7 metric cards
- **Frontend** (`frontend/css/style.css`): Fixed footer bar styles (dark theme, purple accent)
- **Frontend** (`frontend/js/app.js`): `loadMetrics()` function, called on page load + after create/chat/execute/export/rollback
- **Tests** (`tests/test_metrics_api.py`): 8 tests covering all metrics
- **Fix**: Updated `RevertRequest.version_number` from `ge=1` to `ge=0` (v0 now exists)
- Updated CLAUDE.md — added `/api/metrics` to API spec, `global_metrics` to DB schema
- Version bump to v1.1.0

---
