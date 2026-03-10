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
}


def _mock_call_llm(response: dict):
    async def mock(*args, **kwargs):
        return response
    return mock


# ── Versions Tests ───────────────────────────────────────────────────


async def test_list_versions_empty(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "ver-empty"})
    res = await client.get("/api/projects/ver-empty/versions")
    assert res.status_code == 200
    assert res.json() == []


async def test_list_versions_after_chat(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "ver-chat"})

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_PLAN)):
        await client.post(
            "/api/projects/ver-chat/chat",
            json={"message": "trim clip"},
        )

    res = await client.get("/api/projects/ver-chat/versions")
    versions = res.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["is_current"] is True


async def test_list_versions_after_execute(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "ver-exec"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/ver-exec/assets", files=files)

    # Get real clip ID
    proj = await client.get("/api/projects/ver-exec")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan = {
        "assistant_message": "Trimming.",
        "edit_plan": {
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
        "needs_clarification": False,
    }

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post(
            "/api/projects/ver-exec/chat",
            json={"message": "trim clip"},
        )

    # Execute the plan — stays at version 1, marks it executed
    await client.post("/api/projects/ver-exec/execute")

    res = await client.get("/api/projects/ver-exec/versions")
    versions = res.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["is_current"] is True
    assert versions[0]["executed"] is True


async def test_get_version_detail(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "ver-detail"})

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(MOCK_PLAN)):
        await client.post(
            "/api/projects/ver-detail/chat",
            json={"message": "hello"},
        )

    res = await client.get("/api/projects/ver-detail/versions/1")
    assert res.status_code == 200
    data = res.json()
    assert data["version_number"] == 1
    assert len(data["messages"]) == 2  # user + assistant
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "hello"
    assert data["messages"][1]["role"] == "assistant"


async def test_get_version_not_found(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "ver-nf"})
    res = await client.get("/api/projects/ver-nf/versions/99")
    assert res.status_code == 404


async def test_revert_to_version(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "ver-revert"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/ver-revert/assets", files=files)

    # Get real clip ID
    proj = await client.get("/api/projects/ver-revert")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan = {
        "assistant_message": "Trimming.",
        "edit_plan": {
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
        "needs_clarification": False,
    }

    # Create version 1 via chat
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post(
            "/api/projects/ver-revert/chat",
            json={"message": "trim clip"},
        )

    # Execute to mark v1 as executed
    await client.post("/api/projects/ver-revert/execute")

    # Chat again to create version 2 (ensure_version detects executed v1)
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post(
            "/api/projects/ver-revert/chat",
            json={"message": "trim again"},
        )

    # Now we have v1 (executed) and v2 (current)
    versions_res = await client.get("/api/projects/ver-revert/versions")
    versions = versions_res.json()
    assert len(versions) == 2
    assert versions[1]["is_current"] is True

    # Revert to version 1
    res = await client.post(
        "/api/projects/ver-revert/versions/revert",
        json={"version_number": 1},
    )
    assert res.status_code == 200
    assert res.json()["version_number"] == 1
    assert res.json()["is_current"] is True

    # Verify project timeline is restored
    tl_res = await client.get("/api/projects/ver-revert/timeline")
    assert tl_res.json()["timeline"] is not None


async def test_revert_version_not_found(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "ver-rev-nf"})
    res = await client.post(
        "/api/projects/ver-rev-nf/versions/revert",
        json={"version_number": 99},
    )
    assert res.status_code == 404


async def test_versions_project_not_found(client: AsyncClient):
    res = await client.get("/api/projects/nonexistent/versions")
    assert res.status_code == 404
