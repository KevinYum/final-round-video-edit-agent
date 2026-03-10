import io
from unittest.mock import patch

from httpx import AsyncClient


# ── Mock helpers ─────────────────────────────────────────────────────

MOCK_PLAN = {
    "assistant_message": "I'll trim the clip.",
    "edit_plan": {
        "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "c1", "new_in": 0, "new_out": 5}}],
        "summary": "Trim clip",
    },
    "needs_clarification": False,
    "_latency_ms": 150.0,
}

MOCK_CLARIFICATION = {
    "assistant_message": "Could you specify which clip?",
    "edit_plan": None,
    "needs_clarification": True,
    "_latency_ms": 50.0,
}


def _mock_call_llm(response: dict):
    async def mock(*args, **kwargs):
        return dict(response)
    return mock


# ── Tests ────────────────────────────────────────────────────────────


async def test_metrics_initial(client: AsyncClient):
    res = await client.get("/api/metrics")
    assert res.status_code == 200
    m = res.json()
    assert m["total_projects"] == 0
    assert m["total_edit_requests"] == 0
    assert m["successful_edit_requests"] == 0
    assert m["avg_agent_latency_ms"] == 0.0
    assert m["clarification_count"] == 0
    assert m["export_count"] == 0
    assert m["undo_or_recovery_count"] == 0


async def test_metrics_total_projects(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "m1"})
    await client.post("/api/projects", json={"project_id": "m2"})
    res = await client.get("/api/metrics")
    assert res.json()["total_projects"] == 2


async def test_metrics_total_edit_requests(client: AsyncClient):
    """total_edit_requests counts once per version (first message only)."""
    await client.post("/api/projects", json={"project_id": "chat-m"})
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_PLAN)):
        await client.post("/api/projects/chat-m/chat", json={"message": "trim"})
        await client.post("/api/projects/chat-m/chat", json={"message": "trim again"})
    res = await client.get("/api/metrics")
    # Two messages in the same version should only count as 1 edit request
    assert res.json()["total_edit_requests"] == 1


async def test_metrics_avg_latency(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "lat-m"})
    mock1 = dict(MOCK_PLAN, _latency_ms=100.0)
    mock2 = dict(MOCK_PLAN, _latency_ms=200.0)

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(mock1)):
        await client.post("/api/projects/lat-m/chat", json={"message": "edit 1"})
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(mock2)):
        await client.post("/api/projects/lat-m/chat", json={"message": "edit 2"})

    res = await client.get("/api/metrics")
    assert res.json()["avg_agent_latency_ms"] == 150.0


async def test_metrics_clarification(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "clar-m"})
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_CLARIFICATION)):
        await client.post("/api/projects/clar-m/chat", json={"message": "trim something"})
    res = await client.get("/api/metrics")
    assert res.json()["clarification_count"] == 1


async def test_metrics_successful_execute(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "exec-m"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/exec-m/assets", files=files)

    proj = await client.get("/api/projects/exec-m")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan = dict(
        MOCK_PLAN,
        edit_plan={
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
    )

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/exec-m/chat", json={"message": "trim"})
    await client.post("/api/projects/exec-m/execute")

    res = await client.get("/api/metrics")
    assert res.json()["successful_edit_requests"] == 1


async def test_metrics_undo_on_rollback(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "rb-m"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/rb-m/assets", files=files)

    proj = await client.get("/api/projects/rb-m")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan = dict(
        MOCK_PLAN,
        edit_plan={
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
    )

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/rb-m/chat", json={"message": "trim"})
    await client.post("/api/projects/rb-m/execute")
    await client.post("/api/projects/rb-m/rollback")

    res = await client.get("/api/metrics")
    assert res.json()["undo_or_recovery_count"] == 1


async def test_metrics_undo_on_revert(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "rev-m"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/rev-m/assets", files=files)

    proj = await client.get("/api/projects/rev-m")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan = dict(
        MOCK_PLAN,
        edit_plan={
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
    )

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/rev-m/chat", json={"message": "trim"})

    # Revert to v0
    await client.post("/api/projects/rev-m/versions/revert", json={"version_number": 0})

    res = await client.get("/api/metrics")
    assert res.json()["undo_or_recovery_count"] == 1
