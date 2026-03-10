# 交付内容说明

## 1. Runnable code

### One command to run a demo locally

    见下文的Quick Start Section. 根据.env.example配置.env之后，可以通过uv启动server，然后浏览器打开前端可以交互

## 2. README.md

### Design overview

    下面有Claude Code自动生成维护的api, agent flow，和project文件结构。
    简单介绍下核心概念的设计：

    1. Agent设计: LLM在本项目中只用于处理用户需求，生成并迭代一个tool call plan. 这边的tool call是moviePy中需要用到的api包了一层。在进行llm请求时，会把所有available的tool(api)，用户的请求，当前planning，当前session的的聊天历史都传给llm，并让他输出一个会被后端validate的tool_call_plan(list)，或是返回“需要更多的clarification及其原因”。
   
    2. Version设计: 为了支持rollback，每个project都以plan success execution为checkpoint设计version，每个version会保存对应的聊天历史，planning，clip, rendered video都作为version state，rollback就是简单地把相关的state rollback。
   
    3. 其他：基本上就是简单的静态html + fastAPI + sqlite，另外asset, clip, rendered video对应的id在数据库里管理，文件直接在storage/文件夹下

### Trade-offs

    说一下没打磨的点：

    1. API层面的async做了，但是不同project的状态锁没来得及搞，如果多个前端同时edit同一个project可能会有问题
   
    2. 视频的内容理解，作为几小时的take-home，没有想到简单的基于内容理解然后针对其做reasoning & act的方法。

### How to run

    见下面的quick start

### Supported edit operations

    我个人对video edit不是非常熟悉，直接把文档需求给claude让他看着需求把相关的moviePy接口选出来包一包，具体可以看 backend/services/tools.py

    总的来说是根据sdk本身能力和需求可以扩展的

### How AI tools were used

    上面design overview里面写了，主要就是用来生成和迭代planning的

## 3. Demo script

    我后面才发现交付有脚本这么一说，但我现在交互方式，不太方便搞脚本，我等下录个demo视频上传到bilibili会把地址放在这里

## 4. Tests

    用CC开发时，我要求他每一步都写新的tests，没有特意写自己的unit/integration tests

# Video Edit Agent

A FastAPI-based video editing agent that allows users to create projects, upload multi-type assets (video, audio, image), and edit them using natural language. Built with Python, SQLite for project/asset management, and local filesystem for asset storage.

## 1.1. Quick Start

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

## 1.2. Project File Hierarchy

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

## 1.3. Agent Loop Design

The agent follows a create → ingest → chat loop:

1. **Create Project** — User provides project_id, aspect ratio, language. An empty timeline is initialized.
2. **Load Assets** — Upload video/audio/image files. Each asset is classified, metadata extracted (MoviePy/Pillow), and a clip is appended to the timeline with source in/out points.
3. **Conversational Edit** — User sends natural language edit requests via `POST /chat`. The LLM (OpenAI via LangChain) receives the full project context (timeline, assets, 11 available edit tools) and returns a structured edit plan with exact tool parameters, or asks clarifying questions if the request is ambiguous.
4. **Execute Plan** — When the user is satisfied with the plan, clicking Execute (`POST /execute`) creates a new version with a timeline snapshot. Actual tool execution (MoviePy calls) will be added in a future version.
5. **Version Management** — Users can list versions, inspect conversation history per version, and revert to any previous version.

Edit tools span 4 categories: trim/cut/delete, reorder/insert/replace, text overlays/titles/subtitles, and aspect ratio/crop/reframe. Currently plan generation only — tool execution is planned for a future version.

## 1.4. API Endpoints

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

## 1.5. Tech Stack

- **Runtime**: Python 3.13+
- **Package Manager**: uv
- **Backend**: FastAPI + Uvicorn
- **Database**: SQLite (aiosqlite + SQLAlchemy async)
- **Frontend**: Vanilla HTML/CSS/JS
- **Metadata**: MoviePy, Pillow
- **LLM**: LangChain + OpenAI (conversational edit planning)
- **Video Processing**: MoviePy (planned execution)

