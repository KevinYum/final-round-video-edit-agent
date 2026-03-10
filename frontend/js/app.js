const API = "/api/projects";

let currentProjectId = null;

// ── Projects ────────────────────────────────────────────────────────

async function loadProjects() {
    const res = await fetch(API);
    const projects = await res.json();
    const list = document.getElementById("project-list");

    if (projects.length === 0) {
        list.innerHTML = '<p class="empty-state">No projects yet. Create one above!</p>';
        return;
    }

    list.innerHTML = projects
        .map(
            (p) => `
        <div class="project-card" onclick="selectProject('${escapeHtml(p.id)}')">
            <div class="name">${escapeHtml(p.id)}</div>
            <div class="meta">${p.asset_count} asset(s) &middot; ${p.status}${p.target_aspect_ratio ? " &middot; " + p.target_aspect_ratio : ""}</div>
            <div class="meta">${new Date(p.created_at).toLocaleString()}</div>
        </div>
    `
        )
        .join("");
}

async function selectProject(projectId) {
    currentProjectId = projectId;
    const res = await fetch(`${API}/${projectId}`);
    if (!res.ok) return;
    const project = await res.json();

    document.getElementById("project-detail").hidden = false;
    document.getElementById("detail-project-id").textContent = project.id;

    const meta = [];
    if (project.target_aspect_ratio) meta.push(`Aspect: ${project.target_aspect_ratio}`);
    if (project.language) meta.push(`Lang: ${project.language}`);
    meta.push(`Status: ${project.status}`);
    document.getElementById("project-meta").innerHTML = `<p class="meta">${meta.join(" &middot; ")}</p>`;

    renderAssets(project.assets);
    renderTimeline(project.timeline);
    await loadJobs(projectId);

    document.getElementById("project-detail").scrollIntoView({ behavior: "smooth" });
}

function renderAssets(assets) {
    const el = document.getElementById("asset-list");
    if (!assets || assets.length === 0) {
        el.innerHTML = '<p class="empty-state">No assets uploaded yet.</p>';
        return;
    }
    el.innerHTML = `<table class="asset-table">
        <thead><tr><th>Type</th><th>Filename</th><th>Format</th><th>Duration</th><th>Resolution</th><th>Size</th><th></th></tr></thead>
        <tbody>${assets.map((a) => `<tr>
            <td><span class="badge badge-${a.asset_type}">${a.asset_type}</span></td>
            <td>${escapeHtml(a.original_filename)}</td>
            <td>${a.format || "-"}</td>
            <td>${a.duration_seconds != null ? formatTime(a.duration_seconds) : "-"}</td>
            <td>${a.width && a.height ? a.width + "x" + a.height : "-"}</td>
            <td>${a.file_size_bytes ? formatBytes(a.file_size_bytes) : "-"}</td>
            <td><a href="${API}/${currentProjectId}/assets/${a.id}/download" target="_blank">Download</a></td>
        </tr>`).join("")}</tbody>
    </table>`;
}

function renderTimeline(timeline) {
    const el = document.getElementById("timeline-view");
    if (!timeline || !timeline.clips || timeline.clips.length === 0) {
        el.innerHTML = '<p class="empty-state">No clips in timeline. Upload assets to populate.</p>';
        return;
    }

    const rows = timeline.clips.map((clip, i) => {
        const dur = clip.source_out - clip.source_in;
        const tlEnd = clip.timeline_start + dur;
        const res = clip.width && clip.height ? `${clip.width}x${clip.height}` : "-";
        const tx = clip.transcript
            ? `${clip.transcript.segments ? clip.transcript.segments.length : 0} seg(s)`
            : '<span class="meta">none</span>';
        return `<tr>
            <td>${i + 1}</td>
            <td><span class="badge badge-${clip.asset_type || "video"}">${clip.asset_type || "video"}</span></td>
            <td>${escapeHtml(clip.asset_name || clip.asset_id.slice(0, 8))}</td>
            <td>${res}</td>
            <td>${formatTime(clip.source_in)} - ${formatTime(clip.source_out)}</td>
            <td>${formatTime(clip.timeline_start)} - ${formatTime(tlEnd)}</td>
            <td>${formatTime(dur)}</td>
            <td>${tx}</td>
        </tr>`;
    });

    el.innerHTML = `<table class="asset-table">
        <thead><tr><th>#</th><th>Type</th><th>Source Clip</th><th>Resolution</th><th>Source In/Out</th><th>Timeline Position</th><th>Duration</th><th>Transcript</th></tr></thead>
        <tbody>${rows.join("")}</tbody>
    </table>
    <p class="meta" style="margin-top:0.5rem">Total output duration: ${formatTime(timeline.total_duration)}</p>`;
}

async function loadJobs(projectId) {
    const res = await fetch(`${API}/${projectId}/jobs`);
    const jobs = await res.json();
    const el = document.getElementById("job-list");
    if (jobs.length === 0) {
        el.innerHTML = "<li>No edit jobs yet.</li>";
        return;
    }
    el.innerHTML = jobs
        .map(
            (j) => `<li>
            <span class="job-prompt">#${j.id}: ${escapeHtml(j.prompt)}</span>
            <span class="badge badge-${j.status}">${j.status}</span>
        </li>`
        )
        .join("");
}

// ── Create Project ──────────────────────────────────────────────────

document.getElementById("create-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = document.getElementById("create-status");
    const projectId = document.getElementById("project-id-input").value.trim();
    const aspectRatio = document.getElementById("aspect-ratio-input").value || null;
    const language = document.getElementById("language-input").value.trim() || null;

    status.hidden = false;
    status.className = "status info";
    status.textContent = "Creating project...";

    try {
        const res = await fetch(API, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                project_id: projectId,
                target_aspect_ratio: aspectRatio,
                language: language,
            }),
        });
        if (!res.ok) throw new Error(await extractError(res, "Create failed"));

        status.className = "status success";
        status.textContent = `Project "${projectId}" created!`;
        document.getElementById("project-id-input").value = "";
        await loadProjects();
        await selectProject(projectId);
    } catch (err) {
        status.className = "status error";
        status.textContent = `Error: ${err.message}`;
    }
});

// ── Upload Assets ───────────────────────────────────────────────────

document.getElementById("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentProjectId) return;

    const fileInput = document.getElementById("file-input");
    const status = document.getElementById("upload-status");
    if (!fileInput.files.length) return;

    const formData = new FormData();
    for (const file of fileInput.files) {
        formData.append("files", file);
    }

    status.hidden = false;
    status.className = "status info";
    status.textContent = "Uploading assets...";

    try {
        const res = await fetch(`${API}/${currentProjectId}/assets`, {
            method: "POST",
            body: formData,
        });
        if (!res.ok) throw new Error(await extractError(res, "Upload failed"));

        const assets = await res.json();
        status.className = "status success";
        status.textContent = `${assets.length} asset(s) uploaded!`;
        fileInput.value = "";
        await selectProject(currentProjectId);
        await loadProjects();
    } catch (err) {
        status.className = "status error";
        status.textContent = `Error: ${err.message}`;
    }
});

// ── Submit Edit ─────────────────────────────────────────────────────

document.getElementById("edit-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentProjectId) return;

    const prompt = document.getElementById("edit-prompt").value.trim();
    if (!prompt) return;

    const status = document.getElementById("edit-status");
    status.hidden = false;
    status.className = "status info";
    status.textContent = "Submitting edit job...";

    try {
        const res = await fetch(`${API}/${currentProjectId}/edit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt }),
        });
        if (!res.ok) throw new Error(await extractError(res, "Edit failed"));

        const job = await res.json();
        status.className = "status success";
        status.textContent = `Edit job #${job.id} created (status: ${job.status})`;
        document.getElementById("edit-prompt").value = "";
        await loadJobs(currentProjectId);
    } catch (err) {
        status.className = "status error";
        status.textContent = `Error: ${err.message}`;
    }
});

// ── Helpers ─────────────────────────────────────────────────────────

async function extractError(res, fallback) {
    try {
        const body = await res.json();
        if (typeof body.detail === "string") return body.detail;
        if (Array.isArray(body.detail)) {
            return body.detail.map((e) => e.msg || JSON.stringify(e)).join("; ");
        }
        return fallback;
    } catch {
        return fallback;
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = (seconds % 60).toFixed(1);
    return m > 0 ? `${m}m${s}s` : `${s}s`;
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
}

loadProjects();
