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
    assert len(versions) == 2  # v0 (initial snapshot) + v1 (current)
    assert versions[0]["version_number"] == 0
    assert versions[0]["is_current"] is False
    assert versions[0]["executed"] is True
    assert versions[1]["version_number"] == 1
    assert versions[1]["is_current"] is True


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
    assert len(versions) == 2  # v0 + v1
    assert versions[1]["version_number"] == 1
    assert versions[1]["is_current"] is True
    assert versions[1]["executed"] is True


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

    # Now we have v0, v1 (executed), and v2 (current)
    versions_res = await client.get("/api/projects/ver-revert/versions")
    versions = versions_res.json()
    assert len(versions) == 3  # v0 + v1 + v2
    assert versions[2]["is_current"] is True

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


# ── Rollback Tests ──────────────────────────────────────────────────


async def test_rollback_from_v1_to_v0(client: AsyncClient):
    """Rollback from executed v1 should restore v0 timeline and delete v1."""
    await client.post("/api/projects", json={"project_id": "rb-v1"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/rb-v1/assets", files=files)

    proj = await client.get("/api/projects/rb-v1")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]
    original_timeline = proj.json()["timeline"]

    plan = {
        "assistant_message": "Trimming.",
        "edit_plan": {
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
        "needs_clarification": False,
    }

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/rb-v1/chat", json={"message": "trim"})

    await client.post("/api/projects/rb-v1/execute")

    # Now at executed v1, rollback to v0
    res = await client.post("/api/projects/rb-v1/rollback")
    assert res.status_code == 200
    data = res.json()
    assert data["version_number"] == 0
    assert data["timeline"] is not None

    # v1 should be deleted, only v0 remains
    versions_res = await client.get("/api/projects/rb-v1/versions")
    versions = versions_res.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 0
    assert versions[0]["is_current"] is True

    # Project timeline should be restored to original
    proj_after = await client.get("/api/projects/rb-v1")
    assert proj_after.json()["timeline"]["total_duration"] == original_timeline["total_duration"]


async def test_rollback_v0_returns_400(client: AsyncClient):
    """Cannot rollback past v0."""
    await client.post("/api/projects", json={"project_id": "rb-v0"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/rb-v0/assets", files=files)

    plan = {
        "assistant_message": "Trimming.",
        "edit_plan": {
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": "c1", "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
        "needs_clarification": False,
    }

    # Create v0 and v1 via chat
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/rb-v0/chat", json={"message": "trim"})

    # Execute v1 and rollback to v0
    # First need a valid plan to execute - let's just rollback the unexecuted v1
    # Actually, v1 is current and unexecuted, let's test by manually putting us at v0
    # Simpler: rollback from v1 to v0, then try to rollback again from v0
    await client.post("/api/projects/rb-v0/rollback")  # v1 → v0

    # Now at v0, try to rollback again
    res = await client.post("/api/projects/rb-v0/rollback")
    assert res.status_code == 400
    assert "cannot rollback" in res.json()["detail"].lower()


async def test_rollback_deletes_later_versions(client: AsyncClient):
    """Rollback from v2 should delete v2, leaving v0 and v1."""
    await client.post("/api/projects", json={"project_id": "rb-del"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/rb-del/assets", files=files)

    proj = await client.get("/api/projects/rb-del")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan = {
        "assistant_message": "Trimming.",
        "edit_plan": {
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
        "needs_clarification": False,
    }

    # Create v1 via chat, execute it
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/rb-del/chat", json={"message": "trim"})
    await client.post("/api/projects/rb-del/execute")

    # Chat again to create v2
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/rb-del/chat", json={"message": "trim again"})

    # Should have v0, v1, v2
    versions_res = await client.get("/api/projects/rb-del/versions")
    assert len(versions_res.json()) == 3

    # Rollback from v2 to v1
    res = await client.post("/api/projects/rb-del/rollback")
    assert res.status_code == 200
    assert res.json()["version_number"] == 1

    # Only v0 and v1 should remain
    versions_res = await client.get("/api/projects/rb-del/versions")
    versions = versions_res.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 0
    assert versions[1]["version_number"] == 1
    assert versions[1]["is_current"] is True


async def test_rollback_no_versions(client: AsyncClient):
    """Rollback with no versions returns 400."""
    await client.post("/api/projects", json={"project_id": "rb-none"})
    res = await client.post("/api/projects/rb-none/rollback")
    assert res.status_code == 400


async def test_rollback_then_chat_and_execute_again(client: AsyncClient):
    """After rollback, can chat + execute to create a new version at the same number."""
    await client.post("/api/projects", json={"project_id": "rb-round"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/rb-round/assets", files=files)

    proj = await client.get("/api/projects/rb-round")
    clip_id = proj.json()["timeline"]["clips"][0]["id"]

    plan = {
        "assistant_message": "Trimming.",
        "edit_plan": {
            "steps": [{"step_number": 1, "tool_name": "trim_clip", "params": {"clip_id": clip_id, "new_in": 0, "new_out": 5}}],
            "summary": "Trim",
        },
        "needs_clarification": False,
    }

    # v0 + v1 via chat, execute v1
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        await client.post("/api/projects/rb-round/chat", json={"message": "trim"})
    exec_res = await client.post("/api/projects/rb-round/execute")
    assert exec_res.json()["success"] is True

    # Chat again → creates v2
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        chat_res = await client.post("/api/projects/rb-round/chat", json={"message": "trim more"})
    assert chat_res.json()["version_number"] == 2

    # Rollback v2 → v1
    rb_res = await client.post("/api/projects/rb-round/rollback")
    assert rb_res.status_code == 200
    assert rb_res.json()["version_number"] == 1

    # Now chat again → should create v2 again (v1 is executed)
    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan)):
        chat_res2 = await client.post("/api/projects/rb-round/chat", json={"message": "new edit"})
    assert chat_res2.json()["version_number"] == 2

    # Verify versions: v0, v1 (executed), v2 (current, not executed)
    versions_res = await client.get("/api/projects/rb-round/versions")
    versions = versions_res.json()
    assert len(versions) == 3
    assert versions[0]["version_number"] == 0
    assert versions[1]["version_number"] == 1
    assert versions[1]["executed"] is True
    assert versions[2]["version_number"] == 2
    assert versions[2]["is_current"] is True
    assert versions[2]["executed"] is False

    # Execute v2 — should succeed with the clip IDs from v1's timeline
    # Need to get the current clip ID (changed after v1 execution)
    proj2 = await client.get("/api/projects/rb-round")
    new_clip_id = proj2.json()["timeline"]["clips"][0]["id"]

    plan2 = {
        "assistant_message": "Deleting.",
        "edit_plan": {
            "steps": [{"step_number": 1, "tool_name": "delete_clip", "params": {"clip_id": new_clip_id}}],
            "summary": "Delete",
        },
        "needs_clarification": False,
    }

    with patch("backend.services.chat.llm_service.call_llm", new=_mock_call_llm(plan2)):
        await client.post("/api/projects/rb-round/chat", json={"message": "delete it"})

    exec_res2 = await client.post("/api/projects/rb-round/execute")
    assert exec_res2.json()["success"] is True
    assert exec_res2.json()["version_number"] == 2
    assert len(exec_res2.json()["timeline"]["clips"]) == 0


async def test_rollback_project_not_found(client: AsyncClient):
    res = await client.post("/api/projects/nonexistent/rollback")
    assert res.status_code == 404
