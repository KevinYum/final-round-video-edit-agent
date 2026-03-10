const API = "/api/projects";

let currentProjectId = null;
let currentVersionNumber = null;

// ── Player State ────────────────────────────────────────────────────
let player = { clips: [], index: 0, totalDuration: 0 };

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
    renderVideoPreview(project.timeline);
    await loadChatHistory(projectId);

    document.getElementById("project-detail").scrollIntoView({ behavior: "smooth" });
}

function renderAssets(assets) {
    const el = document.getElementById("asset-list");
    if (!assets || assets.length === 0) {
        el.innerHTML = '<p class="empty-state">No assets uploaded yet.</p>';
        return;
    }
    el.innerHTML = `<table class="asset-table">
        <thead><tr><th>Asset ID</th><th>Type</th><th>Filename</th><th>Format</th><th>Duration</th><th>Resolution</th><th>Size</th><th></th></tr></thead>
        <tbody>${assets.map((a) => `<tr>
            <td><code class="id-cell">${escapeHtml(a.id.slice(0, 8))}</code></td>
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
        let tx = '<span class="meta">none</span>';
        if (clip.subtitle_asset_id) {
            tx = `<code class="id-cell">${escapeHtml(clip.subtitle_asset_id.slice(0, 8))}</code>`;
        } else if (clip.transcript) {
            tx = `${clip.transcript.segments ? clip.transcript.segments.length : 0} seg(s)`;
        }
        return `<tr>
            <td><code class="id-cell">${escapeHtml(clip.id)}</code></td>
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
        <thead><tr><th>Clip ID</th><th>Type</th><th>Source</th><th>Resolution</th><th>Source In/Out</th><th>Timeline Position</th><th>Duration</th><th>Transcript</th></tr></thead>
        <tbody>${rows.join("")}</tbody>
    </table>
    <p class="meta" style="margin-top:0.5rem">Total output duration: ${formatTime(timeline.total_duration)}</p>`;
}

function renderVideoPreview(timeline) {
    const el = document.getElementById("video-preview");
    player = { clips: [], index: 0, totalDuration: 0 };

    if (!timeline || !timeline.clips || timeline.clips.length === 0) {
        el.innerHTML = '<p class="empty-state">No video to preview.</p>';
        return;
    }

    const videoClips = timeline.clips.filter((c) => (c.asset_type || "video") === "video");
    if (videoClips.length === 0) {
        el.innerHTML = '<p class="empty-state">No video clips in timeline.</p>';
        return;
    }

    player.clips = videoClips.map((c) => ({
        src: `${API}/${currentProjectId}/assets/${c.asset_id}/download`,
        sourceIn: c.source_in,
        sourceOut: c.source_out,
        name: c.asset_name || c.id,
        dur: c.source_out - c.source_in,
    }));
    player.totalDuration = timeline.total_duration;

    const first = player.clips[0];

    // Build clip segment bar
    let segHtml = "";
    player.clips.forEach((c, i) => {
        segHtml += `<div class="player-seg${i === 0 ? " seg-active" : ""}" data-index="${i}" style="flex:${c.dur}" onclick="playerJumpTo(${i})" title="${escapeHtml(c.name)} (${formatTime(c.dur)})">
            <span class="seg-label">${escapeHtml(c.name)}</span>
        </div>`;
    });

    el.innerHTML = `<div class="player-container">
        <video id="preview-video" controls class="video-player"
               src="${first.src}#t=${first.sourceIn},${first.sourceOut}">
        </video>
        <div class="player-clip-bar">${segHtml}</div>
        <div class="player-info" id="player-info">
            <span id="player-clip-label">Clip 1/${player.clips.length}: ${escapeHtml(first.name)}</span>
            <span class="meta" id="player-clip-range">${formatTime(first.sourceIn)} – ${formatTime(first.sourceOut)}</span>
            <span class="meta" style="margin-left:auto">Total: ${formatTime(player.totalDuration)}</span>
            <button class="export-btn" onclick="exportVideo()" id="export-btn">Export</button>
        </div>
    </div>`;

    const video = document.getElementById("preview-video");
    video.addEventListener("ended", playerAdvance);
}

function renderExportPreview() {
    const el = document.getElementById("video-preview");
    const exportUrl = `${API}/${currentProjectId}/export?t=${Date.now()}`;
    el.innerHTML = `<div class="player-container">
        <video id="preview-video" controls class="video-player" src="${exportUrl}"></video>
        <div class="player-info">
            <span>Rendered v${currentVersionNumber}</span>
            <span class="meta" style="margin-left:auto"></span>
            <button class="export-btn" onclick="exportVideo()" id="export-btn">Download</button>
        </div>
    </div>`;
}

function playerAdvance() {
    if (player.index >= player.clips.length - 1) return;
    player.index++;
    playerLoadClip(player.index, true);
}

function playerJumpTo(index) {
    player.index = index;
    playerLoadClip(index, false);
}

function playerLoadClip(index, autoplay) {
    const clip = player.clips[index];
    if (!clip) return;

    const video = document.getElementById("preview-video");
    video.src = `${clip.src}#t=${clip.sourceIn},${clip.sourceOut}`;
    video.load();
    if (autoplay) video.play();

    // Update info
    document.getElementById("player-clip-label").textContent =
        `Clip ${index + 1}/${player.clips.length}: ${escapeHtml(clip.name)}`;
    document.getElementById("player-clip-range").textContent =
        `${formatTime(clip.sourceIn)} – ${formatTime(clip.sourceOut)}`;

    // Update active segment
    document.querySelectorAll(".player-seg").forEach((el, i) => {
        el.classList.toggle("seg-active", i === index);
    });
}

async function exportVideo() {
    if (!currentProjectId) return;

    const btn = document.getElementById("export-btn");
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Rendering...";
    }

    try {
        const res = await fetch(`${API}/${currentProjectId}/export`);
        if (!res.ok) throw new Error(await extractError(res, "Export failed"));

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${currentProjectId}_v${currentVersionNumber || 0}.mp4`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    } catch (err) {
        alert(`Export failed: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "Export";
        }
    }
}

async function loadChatHistory(projectId) {
    const badge = document.getElementById("chat-version-badge");
    const messagesEl = document.getElementById("chat-messages");
    const planBox = document.getElementById("plan-box");

    // Get versions to find current
    const vRes = await fetch(`${API}/${projectId}/versions`);
    const versions = await vRes.json();
    const current = versions.find((v) => v.is_current);

    if (!current) {
        currentVersionNumber = null;
        badge.hidden = true;
        messagesEl.innerHTML = '<p class="empty-state">Send a message to start editing with AI.</p>';
        planBox.innerHTML = '<p class="empty-state">No plan yet. Chat to generate one.</p>';
        return;
    }

    currentVersionNumber = current.version_number;
    badge.textContent = `v${current.version_number}`;
    badge.hidden = false;

    // Get version detail with messages
    const dRes = await fetch(`${API}/${projectId}/versions/${current.version_number}`);
    const detail = await dRes.json();

    if (!detail.messages || detail.messages.length === 0) {
        messagesEl.innerHTML = '<p class="empty-state">Send a message to start editing with AI.</p>';
        planBox.innerHTML = '<p class="empty-state">No plan yet. Chat to generate one.</p>';
        return;
    }

    // If version was executed, show empty chat, plan with checkmarks, and export preview
    if (current.executed) {
        messagesEl.innerHTML = '<p class="empty-state">Send a message to start editing with AI.</p>';
        renderLatestPlan(detail.messages, true);
        renderExportPreview();
        return;
    }

    renderChatMessages(detail.messages);
    renderLatestPlan(detail.messages);
}

function renderChatMessages(messages) {
    const el = document.getElementById("chat-messages");
    el.innerHTML = messages
        .map((m) => {
            if (m.role === "user") {
                return `<div class="chat-bubble chat-user"><div class="chat-role">You</div><div class="chat-text">${escapeHtml(m.content)}</div></div>`;
            }
            let html = `<div class="chat-bubble chat-assistant"><div class="chat-role">Assistant</div><div class="chat-text">${escapeHtml(m.content)}</div>`;
            if (m.needs_clarification) {
                html += `<div class="chat-clarification">Needs more information to proceed.</div>`;
            }
            html += `</div>`;
            return html;
        })
        .join("");
    el.scrollTop = el.scrollHeight;
}

function renderLatestPlan(messages, executed = false) {
    const planBox = document.getElementById("plan-box");

    // Find the latest assistant message with an edit plan
    let latestPlan = null;
    for (let i = messages.length - 1; i >= 0; i--) {
        const m = messages[i];
        if (m.role === "assistant" && m.edit_plan && m.edit_plan.steps && m.edit_plan.steps.length > 0 && !m.needs_clarification) {
            latestPlan = m.edit_plan;
            break;
        }
    }

    if (!latestPlan) {
        planBox.innerHTML = '<p class="empty-state">No plan yet. Chat to generate one.</p>';
        return;
    }

    if (executed) {
        renderPlanBoxExecuted(latestPlan);
    } else {
        renderPlanBox(latestPlan);
    }
}

function renderPlanBox(plan) {
    const planBox = document.getElementById("plan-box");
    let html = `<ol class="plan-steps">`;
    for (const step of plan.steps) {
        const paramsStr = Object.entries(step.params)
            .map(([k, v]) => `<span class="step-param-key">${escapeHtml(k)}</span>=${escapeHtml(JSON.stringify(v))}`)
            .join(", ");
        html += `<li data-step="${step.step_number}">
            <span class="step-status" id="step-status-${step.step_number}"></span>
            <span class="step-tool">${escapeHtml(step.tool_name)}</span>(<span class="step-params">${paramsStr}</span>)
        </li>`;
    }
    html += `<li class="step-render-item">
        <span class="step-status" id="step-status-render"></span>
        <span class="step-tool">render_video</span>
    </li>`;
    html += `</ol>`;
    html += `<button id="execute-btn" class="execute-btn" onclick="executePlan()">Execute Plan</button>`;
    planBox.innerHTML = html;
}

function renderPlanBoxExecuted(plan) {
    const planBox = document.getElementById("plan-box");
    let html = `<ol class="plan-steps">`;
    for (const step of plan.steps) {
        const paramsStr = Object.entries(step.params)
            .map(([k, v]) => `<span class="step-param-key">${escapeHtml(k)}</span>=${escapeHtml(JSON.stringify(v))}`)
            .join(", ");
        html += `<li data-step="${step.step_number}">
            <span class="step-status step-completed">\u2705</span>
            <span class="step-tool">${escapeHtml(step.tool_name)}</span>(<span class="step-params">${paramsStr}</span>)
        </li>`;
    }
    html += `<li class="step-render-item">
        <span class="step-status step-completed">\u2705</span>
        <span class="step-tool">render_video</span>
    </li>`;
    html += `</ol>`;
    html += `<div class="plan-executed">Plan executed (v${currentVersionNumber}).</div>`;
    planBox.innerHTML = html;
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

// ── Chat ────────────────────────────────────────────────────────────

document.getElementById("chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentProjectId) return;

    const input = document.getElementById("chat-input");
    const message = input.value.trim();
    if (!message) return;

    const sendBtn = document.getElementById("chat-send-btn");
    const messagesEl = document.getElementById("chat-messages");

    // Clear empty state if present
    const emptyState = messagesEl.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    // Append user bubble immediately
    messagesEl.insertAdjacentHTML(
        "beforeend",
        `<div class="chat-bubble chat-user"><div class="chat-role">You</div><div class="chat-text">${escapeHtml(message)}</div></div>`
    );
    messagesEl.scrollTop = messagesEl.scrollHeight;

    input.value = "";
    sendBtn.disabled = true;
    sendBtn.textContent = "Thinking...";

    try {
        const res = await fetch(`${API}/${currentProjectId}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message }),
        });
        if (!res.ok) throw new Error(await extractError(res, "Chat failed"));

        const data = await res.json();

        // Update version badge
        currentVersionNumber = data.version_number;
        const badge = document.getElementById("chat-version-badge");
        badge.textContent = `v${data.version_number}`;
        badge.hidden = false;

        // Render assistant response in chat (text only, no plan inline)
        let html = `<div class="chat-bubble chat-assistant"><div class="chat-role">Assistant</div><div class="chat-text">${escapeHtml(data.assistant_message)}</div>`;
        if (data.needs_clarification) {
            html += `<div class="chat-clarification">Needs more information to proceed.</div>`;
        }
        html += `</div>`;
        messagesEl.insertAdjacentHTML("beforeend", html);
        messagesEl.scrollTop = messagesEl.scrollHeight;

        // Update plan box separately
        if (data.edit_plan && data.edit_plan.steps && data.edit_plan.steps.length > 0 && !data.needs_clarification) {
            renderPlanBox(data.edit_plan);
        }
    } catch (err) {
        messagesEl.insertAdjacentHTML(
            "beforeend",
            `<div class="chat-bubble chat-error"><div class="chat-text">Error: ${escapeHtml(err.message)}</div></div>`
        );
        messagesEl.scrollTop = messagesEl.scrollHeight;
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = "Send";
    }
});

// ── Execute Plan ────────────────────────────────────────────────────

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function executePlan() {
    if (!currentProjectId) return;

    const executeBtn = document.getElementById("execute-btn");
    if (executeBtn) {
        executeBtn.disabled = true;
        executeBtn.textContent = "Executing & Rendering...";
    }

    // Mark all steps as pending
    document.querySelectorAll(".step-status").forEach((el) => {
        el.className = "step-status step-pending";
        el.textContent = "\u23F3";
    });

    try {
        const res = await fetch(`${API}/${currentProjectId}/execute`, {
            method: "POST",
        });
        if (!res.ok) throw new Error(await extractError(res, "Execute failed"));

        const data = await res.json();

        // Animate step statuses one by one
        if (data.step_results) {
            for (const sr of data.step_results) {
                await sleep(300);
                const el = document.getElementById(`step-status-${sr.step_number}`);
                if (!el) continue;
                if (sr.status === "completed") {
                    el.className = "step-status step-completed";
                    el.textContent = "\u2705";
                } else if (sr.status === "failed") {
                    el.className = "step-status step-failed";
                    el.textContent = "\u274C";
                    el.title = sr.error || "Failed";
                }
            }
        }

        if (data.success) {
            // Update timeline and version immediately
            currentVersionNumber = data.version_number;
            const badge = document.getElementById("chat-version-badge");
            badge.textContent = `v${data.version_number}`;
            if (data.timeline) {
                renderTimeline(data.timeline);
            }

            // Set up preview video and wait for it to actually be playable
            const renderEl = document.getElementById("step-status-render");
            const el = document.getElementById("video-preview");
            const exportUrl = `${API}/${currentProjectId}/export?t=${Date.now()}`;
            el.innerHTML = `<div class="player-container">
                <video id="preview-video" controls class="video-player" src="${exportUrl}"></video>
                <div class="player-info">
                    <span>Rendered v${currentVersionNumber}</span>
                    <span class="meta" style="margin-left:auto"></span>
                    <button class="export-btn" onclick="exportVideo()" id="export-btn">Download</button>
                </div>
            </div>`;

            const video = document.getElementById("preview-video");
            await new Promise((resolve) => {
                video.addEventListener("canplay", () => {
                    if (renderEl) {
                        renderEl.className = "step-status step-completed";
                        renderEl.textContent = "\u2705";
                    }
                    resolve();
                }, { once: true });
                video.addEventListener("error", () => {
                    if (renderEl) {
                        renderEl.className = "step-status step-failed";
                        renderEl.textContent = "\u274C";
                        renderEl.title = "Render failed";
                    }
                    resolve();
                }, { once: true });
            });

            // Show success only after render is done
            const planBox = document.getElementById("plan-box");
            const btn = document.getElementById("execute-btn");
            if (btn) btn.remove();
            planBox.insertAdjacentHTML(
                "beforeend",
                `<div class="plan-executed">Plan executed (v${data.version_number}).</div>`
            );

            // Clear chat for new version
            const messagesEl = document.getElementById("chat-messages");
            messagesEl.innerHTML = '<p class="empty-state">Send a message to start editing with AI.</p>';
        } else {

            // Failure: show error but keep plan visible with step statuses
            const planBox = document.getElementById("plan-box");
            planBox.insertAdjacentHTML(
                "beforeend",
                `<div class="plan-error">Error: ${escapeHtml(data.message)}</div>`
            );
            if (executeBtn) {
                executeBtn.disabled = false;
                executeBtn.textContent = "Execute Plan";
            }
        }
    } catch (err) {
        const planBox = document.getElementById("plan-box");
        planBox.insertAdjacentHTML(
            "beforeend",
            `<div class="plan-error">Error: ${escapeHtml(err.message)}</div>`
        );
        if (executeBtn) {
            executeBtn.disabled = false;
            executeBtn.textContent = "Execute Plan";
        }
    }
}

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
