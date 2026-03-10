import io
from unittest.mock import patch

from httpx import AsyncClient


# ── Mock LLM response helpers ───────────────────────────────────────

MOCK_PLAN_RESPONSE = {
    "assistant_message": "I'll trim the first clip to 5 seconds.",
    "edit_plan": {
        "steps": [
            {
                "step_number": 1,
                "tool_name": "trim_clip",
                "params": {"clip_id": "clip-abc", "new_in": 0.0, "new_out": 5.0},
            }
        ],
        "summary": "Trim first clip to 5 seconds",
    },
    "needs_clarification": False,
}

MOCK_CLARIFICATION_RESPONSE = {
    "assistant_message": "Which clip would you like me to trim? You have 3 clips.",
    "edit_plan": None,
    "needs_clarification": True,
}


def _mock_call_llm(response: dict):
    """Create a mock for llm.call_llm that returns the given response."""
    async def mock(*args, **kwargs):
        return response
    return mock


# ── Chat Tests ───────────────────────────────────────────────────────


async def test_chat_returns_plan(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "chat-test"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/chat-test/assets", files=files)

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_PLAN_RESPONSE)):
        res = await client.post(
            "/api/projects/chat-test/chat",
            json={"message": "trim the first clip to 5 seconds"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["assistant_message"] == "I'll trim the first clip to 5 seconds."
    assert data["edit_plan"] is not None
    assert len(data["edit_plan"]["steps"]) == 1
    step = data["edit_plan"]["steps"][0]
    assert step["tool_name"] == "trim_clip"
    assert step["params"]["clip_id"] == "clip-abc"
    assert step["params"]["new_in"] == 0.0
    assert step["params"]["new_out"] == 5.0
    assert "description" not in step  # no description field
    assert data["needs_clarification"] is False
    assert data["version_number"] == 1
    assert "timeline" not in data  # timeline removed from ChatResponse


async def test_chat_does_not_create_version(client: AsyncClient):
    """Chat always plans, never creates new versions by itself."""
    await client.post("/api/projects", json={"project_id": "no-ver-test"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/no-ver-test/assets", files=files)

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_PLAN_RESPONSE)):
        res = await client.post(
            "/api/projects/no-ver-test/chat",
            json={"message": "trim clip"},
        )

    assert res.status_code == 200
    assert res.json()["version_number"] == 1

    # Only version 1 exists (no extra version from chat)
    versions_res = await client.get("/api/projects/no-ver-test/versions")
    versions = versions_res.json()
    assert len(versions) == 1


async def test_chat_needs_clarification(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "clarify-test"})

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_CLARIFICATION_RESPONSE)):
        res = await client.post(
            "/api/projects/clarify-test/chat",
            json={"message": "trim a clip"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["needs_clarification"] is True
    assert data["edit_plan"] is None
    assert "Which clip" in data["assistant_message"]


async def test_chat_conversation_persists(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "history-test"})

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_CLARIFICATION_RESPONSE)):
        await client.post(
            "/api/projects/history-test/chat",
            json={"message": "first message"},
        )
        await client.post(
            "/api/projects/history-test/chat",
            json={"message": "second message"},
        )

    # Check version detail has all messages
    versions_res = await client.get("/api/projects/history-test/versions")
    v = versions_res.json()[0]
    detail_res = await client.get(f"/api/projects/history-test/versions/{v['version_number']}")
    messages = detail_res.json()["messages"]
    assert len(messages) == 4  # 2 user + 2 assistant
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "first message"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "second message"


async def test_chat_project_not_found(client: AsyncClient):
    res = await client.post(
        "/api/projects/nonexistent/chat",
        json={"message": "hello"},
    )
    assert res.status_code == 404


async def test_chat_missing_api_key(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "key-test"})

    with patch("backend.services.llm.OPENAI_API_KEY", ""):
        res = await client.post(
            "/api/projects/key-test/chat",
            json={"message": "hello"},
        )

    assert res.status_code == 500
    assert "API key" in res.json()["detail"]


async def test_chat_no_execution_mode_field(client: AsyncClient):
    """ChatRequest no longer accepts execution_mode."""
    await client.post("/api/projects", json={"project_id": "mode-test"})
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_PLAN_RESPONSE)):
        # Sending execution_mode should be silently ignored (extra fields)
        res = await client.post(
            "/api/projects/mode-test/chat",
            json={"message": "hello", "execution_mode": "apply"},
        )
    # Should still work (Pydantic ignores extra fields by default)
    assert res.status_code == 200


# ── Validation Tests ─────────────────────────────────────────────────


MOCK_INVALID_TOOL_RESPONSE = {
    "assistant_message": "I'll use a magic tool.",
    "edit_plan": {
        "steps": [
            {"step_number": 1, "tool_name": "magic_tool", "params": {"x": 1}},
        ],
        "summary": "Bad plan",
    },
    "needs_clarification": False,
}

MOCK_MISSING_PARAMS_RESPONSE = {
    "assistant_message": "I'll trim the clip.",
    "edit_plan": {
        "steps": [
            {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "c1"}},
        ],
        "summary": "Missing params",
    },
    "needs_clarification": False,
}


async def test_chat_invalid_tool_name_becomes_clarification(client: AsyncClient):
    """If LLM returns an unknown tool name, validation rejects it."""
    await client.post("/api/projects", json={"project_id": "val-tool"})

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_INVALID_TOOL_RESPONSE)):
        res = await client.post(
            "/api/projects/val-tool/chat",
            json={"message": "do something"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["needs_clarification"] is True
    assert data["edit_plan"] is None
    assert "validation failed" in data["assistant_message"].lower()


async def test_chat_missing_required_params_becomes_clarification(client: AsyncClient):
    """If LLM returns a plan with missing required params, validation rejects it."""
    await client.post("/api/projects", json={"project_id": "val-params"})

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_MISSING_PARAMS_RESPONSE)):
        res = await client.post(
            "/api/projects/val-params/chat",
            json={"message": "trim clip"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["needs_clarification"] is True
    assert data["edit_plan"] is None
    assert "new_in" in data["assistant_message"]
    assert "new_out" in data["assistant_message"]


# ── Plan Iteration Tests ─────────────────────────────────────────────


MOCK_PLAN_TWO_STEPS = {
    "assistant_message": "I've added the second trim to the plan.",
    "edit_plan": {
        "steps": [
            {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "clip-abc", "new_in": 0.0, "new_out": 5.0}},
            {"step_number": 2, "tool_name": "trim_clip", "params": {"clip_id": "clip-def", "new_in": 1.0, "new_out": 4.0}},
        ],
        "summary": "Two trims",
    },
    "needs_clarification": False,
}


async def test_chat_passes_current_plan_to_llm(client: AsyncClient):
    """Second chat message should pass the first plan as current_plan to the LLM."""
    await client.post("/api/projects", json={"project_id": "plan-iter"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/plan-iter/assets", files=files)

    captured_kwargs = {}

    async def capturing_mock(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return MOCK_PLAN_TWO_STEPS

    # First chat — no current plan exists yet
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_PLAN_RESPONSE)):
        await client.post(
            "/api/projects/plan-iter/chat",
            json={"message": "trim first clip"},
        )

    # Second chat — should pass the first plan as current_plan
    with patch("backend.services.chat.llm_service.call_llm", new=capturing_mock):
        await client.post(
            "/api/projects/plan-iter/chat",
            json={"message": "also trim the second clip"},
        )

    assert "current_plan" in captured_kwargs
    plan = captured_kwargs["current_plan"]
    assert plan is not None
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["tool_name"] == "trim_clip"
    assert plan["steps"][0]["params"]["clip_id"] == "clip-abc"


async def test_chat_no_current_plan_on_first_message(client: AsyncClient):
    """First chat message should pass current_plan=None to the LLM."""
    await client.post("/api/projects", json={"project_id": "plan-none"})

    captured_kwargs = {}

    async def capturing_mock(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return MOCK_PLAN_RESPONSE

    with patch("backend.services.chat.llm_service.call_llm", new=capturing_mock):
        await client.post(
            "/api/projects/plan-none/chat",
            json={"message": "trim a clip"},
        )

    assert captured_kwargs.get("current_plan") is None


# ── Execute Tests ────────────────────────────────────────────────────


async def test_execute_plan(client: AsyncClient):
    """Execute runs tool steps and creates a new version with updated timeline."""
    await client.post("/api/projects", json={"project_id": "exec-test"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/exec-test/assets", files=files)

    # Get the real clip ID from the timeline
    proj = await client.get("/api/projects/exec-test")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    # Build a plan that references the real clip
    plan_response = {
        "assistant_message": "I'll trim the clip.",
        "edit_plan": {
            "steps": [
                {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0.0, "new_out": 5.0}},
            ],
            "summary": "Trim clip",
        },
        "needs_clarification": False,
    }

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan_response)):
        await client.post(
            "/api/projects/exec-test/chat",
            json={"message": "trim clip"},
        )

    # Execute the plan
    res = await client.post("/api/projects/exec-test/execute")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["version_number"] == 1  # stays at v1 (no new version created)
    assert data["timeline"] is not None
    assert len(data["step_results"]) == 1
    assert data["step_results"][0]["status"] == "completed"

    # Verify timeline was actually mutated (clip trimmed to 5s)
    clip = data["timeline"]["clips"][0]
    assert clip["source_out"] == 5.0
    assert data["timeline"]["total_duration"] == 5.0

    # Verify version 1 is still current and marked as executed
    versions_res = await client.get("/api/projects/exec-test/versions")
    versions = versions_res.json()
    assert len(versions) == 1
    assert versions[0]["is_current"] is True
    assert versions[0]["executed"] is True


async def test_execute_step_failure(client: AsyncClient):
    """Execute with invalid clip_id returns success=false with step error."""
    await client.post("/api/projects", json={"project_id": "exec-fail"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/exec-fail/assets", files=files)

    # Plan references a nonexistent clip
    bad_plan = {
        "assistant_message": "I'll trim a clip.",
        "edit_plan": {
            "steps": [
                {"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "nonexistent", "new_in": 0.0, "new_out": 5.0}},
            ],
            "summary": "Bad trim",
        },
        "needs_clarification": False,
    }

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(bad_plan)):
        await client.post(
            "/api/projects/exec-fail/chat",
            json={"message": "trim clip"},
        )

    res = await client.post("/api/projects/exec-fail/execute")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["version_number"] == 1  # NOT bumped
    assert len(data["step_results"]) == 1
    assert data["step_results"][0]["status"] == "failed"
    assert "not found" in data["step_results"][0]["error"].lower()


async def test_execute_updates_project_timeline(client: AsyncClient):
    """After execute, the project's timeline reflects the changes."""
    await client.post("/api/projects", json={"project_id": "exec-tl"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/exec-tl/assets", files=files)

    proj = await client.get("/api/projects/exec-tl")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan_response = {
        "assistant_message": "Deleting the clip.",
        "edit_plan": {
            "steps": [
                {"step_number": 1, "tool_name": "delete_clip", "params": {"clip_id": clip_id}},
            ],
            "summary": "Delete",
        },
        "needs_clarification": False,
    }

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan_response)):
        await client.post("/api/projects/exec-tl/chat", json={"message": "delete clip"})

    await client.post("/api/projects/exec-tl/execute")

    # Verify the project timeline is updated
    proj_after = await client.get("/api/projects/exec-tl")
    assert len(proj_after.json()["timeline"]["clips"]) == 0
    assert proj_after.json()["timeline"]["total_duration"] == 0.0


async def test_execute_no_plan(client: AsyncClient):
    """Execute with no plan returns 400."""
    await client.post("/api/projects", json={"project_id": "exec-noplan"})

    # Chat with clarification (no plan)
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_CLARIFICATION_RESPONSE)):
        await client.post(
            "/api/projects/exec-noplan/chat",
            json={"message": "trim something"},
        )

    res = await client.post("/api/projects/exec-noplan/execute")
    assert res.status_code == 400
    assert "no plan" in res.json()["detail"].lower()


async def test_execute_no_version(client: AsyncClient):
    """Execute with no version at all returns 400."""
    await client.post("/api/projects", json={"project_id": "exec-nover"})
    res = await client.post("/api/projects/exec-nover/execute")
    assert res.status_code == 400


async def test_execute_project_not_found(client: AsyncClient):
    res = await client.post("/api/projects/nonexistent/execute")
    assert res.status_code == 404
