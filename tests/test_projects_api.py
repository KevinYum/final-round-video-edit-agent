import io

from httpx import AsyncClient


# ── Create Project ───────────────────────────────────────────────────


async def test_create_project(client: AsyncClient):
    res = await client.post(
        "/api/projects",
        json={"project_id": "test-project", "target_aspect_ratio": "16:9", "language": "en"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "test-project"
    assert data["target_aspect_ratio"] == "16:9"
    assert data["language"] == "en"
    assert data["status"] == "created"
    assert data["timeline"] is not None
    assert data["timeline"]["version"] == "0.3.0"
    assert data["timeline"]["clips"] == []
    assert data["timeline"]["total_duration"] == 0.0
    assert data["transcript"] is None
    assert data["assets"] == []


async def test_create_project_minimal(client: AsyncClient):
    res = await client.post("/api/projects", json={"project_id": "minimal"})
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "minimal"
    assert data["target_aspect_ratio"] is None
    assert data["transcript"] is None  # no transcript until provided


async def test_create_project_custom_transcript(client: AsyncClient):
    transcript = {"language": "es", "segments": [{"start": 0, "end": 3, "text": "Hola"}]}
    res = await client.post(
        "/api/projects", json={"project_id": "custom-tx", "transcript": transcript}
    )
    assert res.status_code == 201
    assert res.json()["transcript"] == transcript


async def test_create_project_duplicate(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "dup"})
    res = await client.post("/api/projects", json={"project_id": "dup"})
    assert res.status_code == 409


async def test_create_project_with_spaces(client: AsyncClient):
    res = await client.post("/api/projects", json={"project_id": "my project"})
    assert res.status_code == 201
    assert res.json()["id"] == "my project"


async def test_create_project_invalid_id(client: AsyncClient):
    res = await client.post("/api/projects", json={"project_id": "bad id!"})
    assert res.status_code == 422


# ── List / Get Projects ──────────────────────────────────────────────


async def test_list_projects_empty(client: AsyncClient):
    res = await client.get("/api/projects")
    assert res.status_code == 200
    assert res.json() == []


async def test_list_projects(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "p1"})
    await client.post("/api/projects", json={"project_id": "p2"})
    res = await client.get("/api/projects")
    assert res.status_code == 200
    assert len(res.json()) == 2


async def test_get_project(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "my-proj"})
    res = await client.get("/api/projects/my-proj")
    assert res.status_code == 200
    assert res.json()["id"] == "my-proj"


async def test_get_project_not_found(client: AsyncClient):
    res = await client.get("/api/projects/nonexistent")
    assert res.status_code == 404


# ── Delete Project ───────────────────────────────────────────────────


async def test_delete_project(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "to-delete"})
    res = await client.delete("/api/projects/to-delete")
    assert res.status_code == 204
    res = await client.get("/api/projects/to-delete")
    assert res.status_code == 404


async def test_delete_project_not_found(client: AsyncClient):
    res = await client.delete("/api/projects/nonexistent")
    assert res.status_code == 404


# ── Load Assets ──────────────────────────────────────────────────────


async def test_upload_single_asset(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "asset-test"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    res = await client.post("/api/projects/asset-test/assets", files=files)
    assert res.status_code == 200
    assets = res.json()
    assert len(assets) == 1
    assert assets[0]["asset_type"] == "video"
    assert assets[0]["original_filename"] == "clip.mp4"
    assert assets[0]["file_size_bytes"] > 0


async def test_upload_multiple_assets(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "multi"})
    files = [
        ("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4")),
        ("files", ("bg.mp3", io.BytesIO(b"fake audio"), "audio/mpeg")),
        ("files", ("logo.png", io.BytesIO(b"fake image"), "image/png")),
    ]
    res = await client.post("/api/projects/multi/assets", files=files)
    assert res.status_code == 200
    assets = res.json()
    assert len(assets) == 3
    types = {a["asset_type"] for a in assets}
    assert types == {"video", "audio", "image"}


async def test_upload_assets_project_not_found(client: AsyncClient):
    files = [("files", ("clip.mp4", io.BytesIO(b"fake"), "video/mp4"))]
    res = await client.post("/api/projects/nope/assets", files=files)
    assert res.status_code == 404


# ── Timeline auto-population ─────────────────────────────────────────


async def test_timeline_populated_after_asset_upload(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "tl-test"})
    files = [("files", ("clip.mp4", io.BytesIO(b"fake video"), "video/mp4"))]
    await client.post("/api/projects/tl-test/assets", files=files)

    res = await client.get("/api/projects/tl-test/timeline")
    assert res.status_code == 200
    tl = res.json()["timeline"]
    assert len(tl["clips"]) == 1
    assert tl["total_duration"] > 0

    clip = tl["clips"][0]
    assert clip["source_in"] == 0.0
    assert clip["timeline_start"] == 0.0
    assert clip["asset_name"] == "clip.mp4"

    # Check project status updated to active
    proj_res = await client.get("/api/projects/tl-test")
    assert proj_res.json()["status"] == "active"


async def test_timeline_multiple_clips_sequential(client: AsyncClient):
    """Upload multiple files in a single request — all added to empty timeline."""
    await client.post("/api/projects", json={"project_id": "tl-multi"})
    files = [
        ("files", ("a.mp4", io.BytesIO(b"vid1"), "video/mp4")),
        ("files", ("b.mp4", io.BytesIO(b"vid2"), "video/mp4")),
    ]
    await client.post("/api/projects/tl-multi/assets", files=files)

    res = await client.get("/api/projects/tl-multi/timeline")
    tl = res.json()["timeline"]
    assert len(tl["clips"]) == 2

    # Second clip starts after first ends
    clip1 = tl["clips"][0]
    clip2 = tl["clips"][1]
    clip1_dur = clip1["source_out"] - clip1["source_in"]
    assert clip2["timeline_start"] == clip1["timeline_start"] + clip1_dur


async def test_second_upload_does_not_modify_timeline(client: AsyncClient):
    """Subsequent uploads after first should not auto-add to timeline."""
    await client.post("/api/projects", json={"project_id": "tl-no-auto"})
    files1 = [("files", ("a.mp4", io.BytesIO(b"vid1"), "video/mp4"))]
    await client.post("/api/projects/tl-no-auto/assets", files=files1)

    res = await client.get("/api/projects/tl-no-auto/timeline")
    assert len(res.json()["timeline"]["clips"]) == 1

    # Second upload should NOT add to timeline
    files2 = [("files", ("b.mp4", io.BytesIO(b"vid2"), "video/mp4"))]
    await client.post("/api/projects/tl-no-auto/assets", files=files2)

    res = await client.get("/api/projects/tl-no-auto/timeline")
    assert len(res.json()["timeline"]["clips"]) == 1  # still 1


async def test_timeline_subtitle_excluded(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "tl-sub"})
    files = [
        ("files", ("clip.mp4", io.BytesIO(b"vid"), "video/mp4")),
        ("files", ("subs.srt", io.BytesIO(b"subtitle data"), "text/plain")),
    ]
    await client.post("/api/projects/tl-sub/assets", files=files)

    res = await client.get("/api/projects/tl-sub/timeline")
    tl = res.json()["timeline"]
    # Only the video should be a clip, not the subtitle
    assert len(tl["clips"]) == 1


# ── List Assets ──────────────────────────────────────────────────────


async def test_list_assets(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "list-a"})
    files = [
        ("files", ("a.mp4", io.BytesIO(b"vid"), "video/mp4")),
        ("files", ("b.png", io.BytesIO(b"img"), "image/png")),
    ]
    await client.post("/api/projects/list-a/assets", files=files)

    res = await client.get("/api/projects/list-a/assets")
    assert res.status_code == 200
    assert len(res.json()) == 2


# ── Edit Jobs ────────────────────────────────────────────────────────


async def test_create_edit_job(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "edit-test"})
    files = [("files", ("clip.mp4", io.BytesIO(b"vid"), "video/mp4"))]
    await client.post("/api/projects/edit-test/assets", files=files)

    res = await client.post(
        "/api/projects/edit-test/edit",
        json={"prompt": "trim the first 5 seconds"},
    )
    assert res.status_code == 200
    job = res.json()
    assert job["status"] == "pending"
    assert job["prompt"] == "trim the first 5 seconds"
    assert job["timeline_before"] is not None
    assert job["timeline_before"]["clips"] is not None


async def test_create_edit_job_project_not_found(client: AsyncClient):
    res = await client.post("/api/projects/nope/edit", json={"prompt": "test"})
    assert res.status_code == 404


async def test_list_edit_jobs(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "jobs-test"})
    await client.post("/api/projects/jobs-test/edit", json={"prompt": "edit 1"})
    await client.post("/api/projects/jobs-test/edit", json={"prompt": "edit 2"})

    res = await client.get("/api/projects/jobs-test/jobs")
    assert res.status_code == 200
    assert len(res.json()) == 2


# ── Delete project cascades ──────────────────────────────────────────


async def test_delete_project_cascades_assets(client: AsyncClient):
    await client.post("/api/projects", json={"project_id": "cascade"})
    files = [("files", ("clip.mp4", io.BytesIO(b"vid"), "video/mp4"))]
    await client.post("/api/projects/cascade/assets", files=files)

    res = await client.delete("/api/projects/cascade")
    assert res.status_code == 204

    res = await client.get("/api/projects/cascade/assets")
    # Project not found means assets gone too
    assert res.json() == []
