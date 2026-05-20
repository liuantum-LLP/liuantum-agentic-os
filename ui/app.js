const API_BASE = localStorage.getItem("LIUANT_API_BASE") || "http://127.0.0.1:8000";
const nativeFetch = window.fetch.bind(window);
window.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;
  const headers = new Headers(init.headers || {});
  const token = localStorage.getItem("LIUANT_API_TOKEN");
  const session = localStorage.getItem("LIUANT_SESSION_TOKEN");
  if (url && url.startsWith(API_BASE)) {
    if (token && !headers.has("authorization")) headers.set("authorization", `Bearer ${token}`);
    if (session && !headers.has("x-liuant-session")) headers.set("x-liuant-session", session);
  }
  let response = await nativeFetch(input, { ...init, headers });
  if (response.status === 401 && url && url.startsWith(API_BASE)) {
    const entered = window.prompt("Enter your local Liuant API token");
    if (entered) {
      localStorage.setItem("LIUANT_API_TOKEN", entered);
      headers.set("authorization", `Bearer ${entered}`);
      response = await nativeFetch(input, { ...init, headers });
    }
  }
  return response;
};

const pageEndpoints = {
  dashboard: ["/api/system/dashboard"],
  agents: ["/api/agents", "/api/agents/runs"],
  "agent-builder": ["/api/agents", "/api/automations/"],
  connectors: ["/api/connectors", "/api/social/connectors", "/api/telegram/status", "/api/telegram/messages", "/api/telegram/drafts"],
  "social-studio": ["/api/social/connectors", "/api/social/campaigns", "/api/social/drafts"],
  "content-calendar": ["/api/social/campaigns"],
  "approval-queue": ["/api/approvals"],
  "image-studio": ["/api/generation/image/providers", "/api/generation/image/jobs"],
  "video-studio": ["/api/generation/video/providers", "/api/generation/video/jobs"],
  "email-assistant": ["/api/email/gmail/status", "/api/email/drafts"],
  "automation-studio": ["/api/scheduler/status", "/api/automations/", "/api/scheduler/runs"],
  settings: ["/api/settings"],
  permissions: ["/api/permissions/status", "/api/permissions/rules"],
  skills: ["/api/skills/available", "/api/skills/installed"],
  workspaces: ["/api/workspaces", "/api/exports"],
  onboarding: ["/api/onboarding/status"],
  "provider-setup": ["/api/providers/status", "/api/providers"],
  memory: ["/api/memory"],
  "knowledge-base": ["/api/knowledge/sources"],
  verification: ["/api/auth/status", "/api/secrets/status", "/api/verify/status", "/api/env/check", "/api/backup/list"],
  release: ["/api/release/status", "/api/desktop/status", "/api/signing/status", "/api/update/info"],
};

async function loadLiveData() {
  const page = document.body.dataset.page;
  const endpoints = pageEndpoints[page] || [];
  const main = document.querySelector(".main");
  if (!main || endpoints.length === 0) return;

  let live = document.querySelector(".live-data");
  if (!live) {
    live = document.createElement("section");
    live.className = "live-data";
    main.appendChild(live);
  }

  live.innerHTML = liveHeader(page) + `<div class="state loading">Loading live data from ${API_BASE}</div>`;

  try {
    const results = await Promise.all(endpoints.map(fetchEndpoint));
    live.innerHTML = liveHeader(page) + results.map((result) => renderEndpoint(page, result.endpoint, result.data)).join("");
    wireApprovalButtons();
    wireSettingsButtons();
    wireWorkflowSettings();
    wirePermissionButtons();
    wireModeToggles();
    wireImageGenerateButton();
    wireVideoButtons();
    wireSocialCampaignForm();
    wireAgentCreateForm();
    wireEmailDraftForm();
    wireAutomationForm();
    wireSkillButtons();
    wireWorkspaceButtons();
    wireProviderButtons();
    wireAgentRunForm();
    wireTelegramButtons();
    wireSocialConnectorButtons();
    wireSocialDraftButtons();
    wireMemoryButtons();
    wireKnowledgeButtons();
    wireVerificationButtons();
    wireReleaseButtons();
    toast("Live data refreshed");
  } catch (error) {
    live.innerHTML =
      liveHeader(page) +
      `<div class="state error"><strong>API unavailable.</strong><span>Start it with <code>uvicorn runtime.api.app:app --reload</code>.</span><pre>${escapeHtml(String(error))}</pre></div>`;
  }
}

async function fetchEndpoint(endpoint) {
  const response = await fetch(`${API_BASE}${endpoint}`);
  if (!response.ok) throw new Error(`${endpoint}: ${response.status}`);
  return { endpoint, data: await response.json() };
}

function liveHeader(page) {
  return `<div class="live-head"><div><h2>Live ${title(page)}</h2><p>SQLite-backed MVP data</p></div><button id="refresh-live" onclick="loadLiveData()">Refresh</button></div>`;
}

function renderEndpoint(page, endpoint, data) {
  if (page === "dashboard") return renderDashboard(data);
  if (page === "approval-queue") return renderApprovals(data);
  if (page === "settings") return renderSettings(data);
  if (page === "permissions") return renderPermissions(endpoint, data);
  if (page === "skills") return renderSkills(endpoint, data);
  if (page === "workspaces") return renderWorkspaces(endpoint, data);
  if (page === "provider-setup") return renderProviders(endpoint, data);
  if (page === "memory") return renderMemory(data);
  if (page === "knowledge-base") return renderKnowledge(endpoint, data);
  if (page === "verification") return renderVerification(endpoint, data);
  if (page === "release") return renderRelease(endpoint, data);
  if (endpoint === "/api/social/connectors") return renderSocialConnectors(data);
  if (endpoint === "/api/social/drafts") return renderSocialDrafts(data);
  if (page === "email-assistant" && endpoint === "/api/email/gmail/status") return renderGmailStatus(data);
  if (page === "image-studio" && endpoint === "/api/generation/image/providers") return renderImageProviders(data);
  if (page === "automation-studio" && endpoint === "/api/scheduler/status") return renderSchedulerStatus(data);
  if (page === "automation-studio" && endpoint === "/api/automations/") return renderAutomations(data);
  if (page === "automation-studio" && endpoint === "/api/scheduler/runs") return renderAutomationRuns(data);
  if (page === "image-studio" && endpoint === "/api/generation/image/jobs") return renderImageJobs(data);
  if (page === "video-studio" && endpoint === "/api/generation/video/jobs") return renderVideoJobs(data);
  if (Array.isArray(data)) return renderCards(endpoint, data);
  if (data && typeof data === "object") {
    if (endpoint === "/api/connectors") return renderConnectors(data);
    if (endpoint === "/api/telegram/status") return renderTelegramStatus(data);
    return `<article class="data-card"><h3>${endpoint}</h3><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre></article>`;
  }
  return `<article class="data-card"><h3>${endpoint}</h3><p>${escapeHtml(String(data))}</p></article>`;
}

function renderSkills(endpoint, rows) {
  if (!rows.length) return `<div class="state empty">${endpoint} has no skill records yet.</div>`;
  const installed = endpoint.endsWith("/installed");
  return `<h3>${installed ? "Installed Skills" : "Available Skills"}</h3><div class="data-grid">${rows.map((skill) => `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(skill.category || skill.status || "skill")}</span><span>${escapeHtml(skill.safety_level || "safe")}</span></div><h3>${escapeHtml(skill.title || skill.skill_name)}</h3><p>${escapeHtml(skill.description || "")}</p><p><strong>Tools:</strong> ${escapeHtml((skill.required_tools_json || []).join(", ") || "-")}</p><div class="row">${installed ? `<button data-skill-action="enable" data-skill="${escapeHtml(skill.skill_name)}">Enable</button><button class="secondary" data-skill-action="disable" data-skill="${escapeHtml(skill.skill_name)}">Disable</button>` : `<button data-skill-action="install" data-skill="${escapeHtml(skill.skill_name)}">Install</button>`}</div><pre>${escapeHtml(JSON.stringify(skill, null, 2))}</pre></article>`).join("")}</div>`;
}

function renderWorkspaces(endpoint, data) {
  if (endpoint === "/api/exports") return renderCards(endpoint, data);
  if (!data.length) return `<div class="state empty">No workspace records yet.</div>`;
  return `<h3>Workspaces</h3><div class="data-grid">${data.map((row) => `<article class="data-card"><div class="card-row"><span class="pill">${row.is_default ? "default" : "workspace"}</span></div><h3>${escapeHtml(row.name)}</h3><p>${escapeHtml(row.path)}</p><button data-workspace-default="${escapeHtml(row.name)}" ${row.is_default ? "disabled" : ""}>Set Default</button></article>`).join("")}</div>`;
}

function renderProviders(endpoint, data) {
  if (endpoint === "/api/providers/status") {
    const defaults = data.defaults || {};
    return `<article class="data-card"><h3>Model Hub Overview</h3>
      <div class="stat-grid compact">
        <article class="stat"><span>Providers</span><strong>${data.provider_count || 0}</strong></article>
        <article class="stat"><span>Configured</span><strong>${data.configured_count || 0}</strong></article>
        <article class="stat"><span>Missing Keys</span><strong>${data.missing_key_count || 0}</strong></article>
        <article class="stat"><span>Local Enabled</span><strong>${data.local_enabled_count || 0}</strong></article>
      </div>
      <p><strong>Defaults:</strong> ${Object.entries(defaults).map(([key, value]) => `${escapeHtml(key)}=${escapeHtml(value || "-")}`).join(" · ")}</p>
      <pre>${escapeHtml(JSON.stringify({ defaults: data.defaults, fallbacks: data.fallbacks }, null, 2))}</pre>
    </article>`;
  }
  if (!data.length) return `<div class="state empty">No providers configured.</div>`;
  const tabs = ["text", "image", "video", "embedding", "speech_to_text", "text_to_speech"];
  return `<h3>Model Hub Providers</h3><div class="provider-tabs">${tabs.map((tab) => `<span class="pill">${escapeHtml(tab)}</span>`).join("")}</div><div class="data-grid">${data.map((provider) => {
    const caps = provider.capabilities || {};
    const local = caps.local ? "local" : "cloud";
    const setup = provider.status === "missing_key" ? `Add ${escapeHtml(provider.api_key_env || "provider key")} to <code>.env</code>, <code>.env.local</code>, or your environment.` : (provider.notes || provider.setup_instruction || "");
    return `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(provider.status)}</span><span>${escapeHtml(provider.category || "provider")}</span><span>${escapeHtml(local)}</span>${provider.is_default ? `<span>Default</span>` : ""}</div><h3>${escapeHtml(provider.display_name || provider.name)}</h3><p><strong>ID:</strong> ${escapeHtml(provider.id || provider.name)}</p><p><strong>Model:</strong> ${escapeHtml(provider.default_model || "-")}</p><p><strong>Key:</strong> ${escapeHtml(provider.api_key_masked || "not set")}</p><p><strong>Base URL:</strong> ${escapeHtml(provider.base_url || "-")}</p><p><strong>Enabled:</strong> ${provider.is_enabled ? "Yes" : "No"}</p>${setup ? `<p><strong>Setup:</strong> ${setup}</p>` : ""}<div class="row"><button data-provider-test="${escapeHtml(provider.id)}">Test Config</button>${provider.category === "text" ? `<button class="secondary" data-provider-generate-test="${escapeHtml(provider.id)}" data-provider-model="${escapeHtml(provider.default_model || "")}">Generate Test Text</button>` : ""}<button class="secondary" data-provider-toggle="${escapeHtml(provider.id)}" data-enabled="${provider.is_enabled ? "false" : "true"}">${provider.is_enabled ? "Disable" : "Enable"}</button><button class="secondary" data-provider-default="${escapeHtml(provider.id)}" data-provider-category="${escapeHtml(provider.category || "text")}">Set Default</button><button class="secondary" data-provider-fallback="${escapeHtml(provider.id)}" data-provider-category="${escapeHtml(provider.category || "text")}">Set Fallback</button></div></article>`;
  }).join("")}</div>`;
}

function renderImageProviders(rows) {
  if (!rows.length) return `<div class="state empty">No image providers registered.</div>`;
  return `<h3>Image Provider Status</h3><div class="data-grid">${rows.map((provider) => `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(provider.status || provider.provider_status || "unknown")}</span><span>${provider.configured ? "Configured" : "Missing key"}</span></div><h3>${escapeHtml(provider.display_name)}</h3><p><strong>Default model:</strong> ${escapeHtml(provider.default_model || "-")}</p><p><strong>Env:</strong> ${escapeHtml((provider.env_vars || []).join(", ") || "-")}</p>${provider.setup_instruction ? `<p><strong>Setup:</strong> ${escapeHtml(provider.setup_instruction)}</p>` : ""}</article>`).join("")}</div>`;
}

function renderGmailStatus(data) {
  return `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(data.status)}</span><span>${data.authorized ? "Authorized" : "Not connected"}</span></div><h3>Gmail Connection</h3><p><strong>Account:</strong> ${escapeHtml(data.account_email || "-")}</p><p><strong>Token expires:</strong> ${escapeHtml(data.token_expires_at || "-")}</p><p><strong>Sending:</strong> Disabled</p><pre>${escapeHtml(JSON.stringify(data.setup_instructions || [], null, 2))}</pre></article>`;
}

function renderAutomations(rows) {
  if (!rows.length) return `<div class="state empty">No automations yet. Create one above.</div>`;
  return `<h3>Automations</h3><div class="data-grid">${rows.map((row) => `<article class="data-card"><div class="card-row"><span class="pill">${row.enabled ? "enabled" : "disabled"}</span><span>${escapeHtml(row.trigger_type)}</span></div><h3>${escapeHtml(row.name)}</h3><p>${escapeHtml(row.task_prompt)}</p><p><strong>Schedule:</strong> ${escapeHtml(row.schedule_text || "-")}</p><p><strong>Next run:</strong> ${escapeHtml(row.next_run_at || "-")}</p><p><strong>Last run:</strong> ${escapeHtml(row.last_run_at || "-")}</p><p><strong>Runs:</strong> ${escapeHtml(row.run_count || 0)} · <strong>Failures:</strong> ${escapeHtml(row.failure_count || 0)}</p><div class="row"><button data-automation-run="${escapeHtml(row.id)}">Run Now</button><button class="secondary" data-automation-toggle="${escapeHtml(row.id)}" data-enabled="${row.enabled ? "false" : "true"}">${row.enabled ? "Disable" : "Enable"}</button></div></article>`).join("")}</div>`;
}

function renderSchedulerStatus(data) {
  return `<article class="data-card"><div class="card-row"><span class="pill">${data.enabled ? "enabled" : "disabled"}</span><span>${escapeHtml(data.mode || "local")}</span></div><h3>Scheduler Status</h3><div class="stat-grid compact"><article class="stat"><span>Due</span><strong>${data.due_count || 0}</strong></article><article class="stat"><span>Enabled</span><strong>${data.enabled_automation_count || 0}</strong></article></div><p><strong>Next due:</strong> ${escapeHtml(data.next_due_at || "-")}</p><p><strong>Last tick:</strong> ${escapeHtml(data.last_tick_at || "-")}</p><p>Automations create local reports and drafts only. External sending/publishing remains disabled unless future explicit approval settings are added.</p><div class="row"><button data-scheduler-action="tick">Tick</button><button class="secondary" data-scheduler-action="run-due">Run Due</button></div><pre>${escapeHtml(JSON.stringify(data.warnings || [], null, 2))}</pre></article>`;
}

function renderAutomationRuns(rows) {
  if (!rows.length) return `<div class="state empty">No automation run history yet.</div>`;
  return `<h3>Run History</h3><div class="data-grid">${rows.map((row) => `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(row.status)}</span><span>${escapeHtml(row.reason || "manual")}</span></div><h3>${escapeHtml(row.automation_id)}</h3><p><strong>Started:</strong> ${escapeHtml(row.started_at || "-")}</p><p><strong>Completed:</strong> ${escapeHtml(row.completed_at || "-")}</p><p><strong>Output:</strong> ${escapeHtml(row.output_path || "-")}</p><p><strong>Approvals:</strong> ${escapeHtml((row.approvals_json || []).join(", ") || "-")}</p></article>`).join("")}</div>`;
}

function renderImageJobs(rows) {
  if (!rows.length) return `<div class="state empty">No image jobs yet.</div>`;
  return `<h3>Image Jobs</h3><div class="data-grid">${rows.map((job) => {
    const isImage = job.output_path && /\.(png|jpg|jpeg|webp)$/i.test(job.output_path);
    const fileUrl = isImage ? `file://${job.output_path}` : "";
    return `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(job.status)}</span><span>${escapeHtml(job.generation_mode || "model_based")}</span><span>${escapeHtml(job.provider)}</span></div><h3>${escapeHtml(job.prompt)}</h3>${isImage ? `<img class="preview" src="${escapeHtml(fileUrl)}" alt="Generated image"/>` : ""}${job.setup_instruction ? `<p><strong>Setup:</strong> ${escapeHtml(job.setup_instruction)}</p>` : ""}<p><strong>Render type:</strong> ${escapeHtml(job.render_type || "-")}</p><p><strong>Output:</strong> ${escapeHtml(job.output_path || "-")}</p><p><strong>Package:</strong> ${escapeHtml(job.output_package_path || "-")}</p><pre>${escapeHtml(JSON.stringify(job.metadata || {}, null, 2))}</pre></article>`;
  }).join("")}</div>`;
}

function renderVideoJobs(rows) {
  if (!rows.length) return `<div class="state empty">No video jobs yet.</div>`;
  return `<h3>Video Jobs</h3><div class="data-grid">${rows.map((job) => {
    const isVideo = job.output_path && /\.(mp4|webm|mov)$/i.test(job.output_path);
    const fileUrl = isVideo ? `file://${job.output_path}` : "";
    return `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(job.status)}</span><span>${escapeHtml(job.generation_mode || "model_based")}</span><span>${escapeHtml(job.provider)}</span></div><h3>${escapeHtml(job.prompt)}</h3>${isVideo ? `<video class="preview" src="${escapeHtml(fileUrl)}" controls></video>` : ""}<p><strong>Model:</strong> ${escapeHtml(job.model || "-")}</p><p><strong>Provider job:</strong> ${escapeHtml(job.provider_job_id || "-")}</p><p><strong>Provider URL:</strong> ${job.provider_output_url ? `<a href="${escapeHtml(job.provider_output_url)}">${escapeHtml(job.provider_output_url)}</a>` : "-"}</p><p><strong>Render type:</strong> ${escapeHtml(job.render_type || "-")}</p><p><strong>Skill:</strong> ${escapeHtml(job.skill_name || "-")}</p><p><strong>Platform:</strong> ${escapeHtml(job.platform || "-")}</p><p><strong>Output:</strong> ${escapeHtml(job.output_path || "-")}</p><p><strong>Package:</strong> ${escapeHtml(job.output_package_path || "-")}</p>${job.error ? `<p><strong>Error:</strong> ${escapeHtml(job.error)}</p>` : ""}<div class="row"><button data-video-action="poll" data-job="${escapeHtml(job.id)}">Poll</button><button class="secondary" data-video-action="download" data-job="${escapeHtml(job.id)}">Download</button><button class="secondary" data-video-action="export" data-job="${escapeHtml(job.id)}">Export</button><button class="secondary" data-video-action="cancel" data-job="${escapeHtml(job.id)}">Cancel</button></div><pre>${escapeHtml(JSON.stringify(job.metadata || {}, null, 2))}</pre></article>`;
  }).join("")}</div>`;
}

function renderSettings(rows) {
  if (!rows.length) return `<div class="state empty">No settings found.</div>`;
  return `<div class="data-grid">${rows.map((row) => `<article class="data-card"><h3>${escapeHtml(row.key)}</h3><input value="${escapeHtml(row.value)}" data-setting-value="${escapeHtml(row.key)}"/><button data-setting="${escapeHtml(row.key)}">Save</button></article>`).join("")}</div>`;
}

function renderMemory(rows) {
  return `<article class="data-card stack"><h3>Add Memory</h3><textarea id="memory-content" placeholder="Remember..."></textarea><select id="memory-type"><option value="user">user</option><option value="project">project</option><option value="agent">agent</option><option value="task">task</option></select><button id="add-memory">Add Memory</button><input id="memory-query" placeholder="Search memory" /><button id="search-memory">Search</button></article>${renderCards("/api/memory", rows)}`;
}

function renderKnowledge(endpoint, rows) {
  return `<article class="data-card stack"><h3>Knowledge Base</h3><textarea id="knowledge-text" placeholder="Add local knowledge text"></textarea><button id="add-knowledge">Add Text</button><input id="knowledge-file" placeholder="workspace/path/to/file.md" /><button id="index-knowledge-file">Index File</button><input id="knowledge-query" placeholder="Search knowledge" /><button id="search-knowledge">Search</button><pre id="knowledge-output"></pre></article>${renderCards(endpoint, rows)}`;
}

function renderVerification(endpoint, data) {
  if (endpoint === "/api/auth/status") {
    return `<article class="data-card stack"><h3>Local API Auth</h3><div class="card-row"><span class="pill">${escapeHtml(data.status)}</span><span>${escapeHtml(data.token_status || "missing")}</span></div><p><strong>Token backend:</strong> ${escapeHtml(data.token_backend || "-")}</p><p><strong>Sessions:</strong> ${escapeHtml(data.active_session_count || 0)}</p><div class="row"><button data-auth-action="rotate-token">Rotate Token</button><button class="secondary" data-auth-action="logout">Logout</button></div></article>`;
  }
  if (endpoint === "/api/secrets/status") {
    return `<article class="data-card stack"><h3>Secret Storage</h3><div class="card-row"><span class="pill">${escapeHtml(data.default_backend || "unknown")}</span><span>${escapeHtml(data.stored_secret_count || 0)} stored</span></div><p><strong>Keyring:</strong> ${data.keyring_available ? "available" : "not available"}</p><p><strong>Warnings:</strong> ${escapeHtml((data.unmigrated_secret_warnings || []).length)}</p><div class="row"><button data-secret-action="migrate">Migrate Secrets</button><button class="secondary" data-verify="security">Run Secret Audit</button><button class="secondary" data-backup-action="create">Create Backup</button></div><pre>${escapeHtml(JSON.stringify(data.unmigrated_secret_warnings || [], null, 2))}</pre></article>`;
  }
  if (endpoint === "/api/verify/status") {
    const rows = data.latest || [];
    return `<article class="data-card stack"><h3>Verification Center</h3><p>Run live-safe provider, connector, storage, and security checks. Media generation is not triggered unless explicitly requested from the CLI/API.</p><div class="row"><button data-verify="all">Run All</button><button class="secondary" data-verify="providers">Providers</button><button class="secondary" data-verify="security">Security</button><button class="secondary" data-verify="storage">Storage</button></div></article>${renderCards(endpoint, rows)}`;
  }
  return renderCards(endpoint, Array.isArray(data) ? data : [data]);
}

function renderRelease(endpoint, data) {
  if (endpoint === "/api/release/status") {
    return `<article class="data-card stack"><h3>Release Overview</h3><div class="card-row"><span class="pill">${escapeHtml(data.version?.app_version || "-")}</span><span>${escapeHtml(data.version?.channel || "local-mvp")}</span></div><p><strong>Platform:</strong> ${escapeHtml(data.version?.platform || "-")}</p><p><strong>Desktop:</strong> ${escapeHtml(data.desktop?.status || "-")}</p><p><strong>Signing:</strong> ${data.signing?.signed ? "signed" : "unsigned"}</p><div class="row"><button data-release-action="release-check">Run Release Check</button><button class="secondary" data-release-action="desktop-check">Desktop Check</button><button class="secondary" data-release-action="signing-check">Signing Check</button></div><pre>${escapeHtml(JSON.stringify(data.paths || {}, null, 2))}</pre></article>`;
  }
  if (endpoint === "/api/desktop/status") {
    return `<article class="data-card stack"><h3>Desktop Packaging</h3><div class="card-row"><span class="pill">${escapeHtml(data.status)}</span><span>${data.tauri_project_exists ? "Tauri detected" : "No Tauri project yet"}</span></div><p><strong>Root:</strong> ${escapeHtml(data.desktop_root || "-")}</p><p><strong>Config:</strong> ${escapeHtml(data.tauri_config || "-")}</p><p><strong>Node:</strong> ${data.node_available ? "available" : "missing"} · <strong>Cargo:</strong> ${data.cargo_available ? "available" : "missing"}</p><pre>${escapeHtml(JSON.stringify(data.setup_instructions || [], null, 2))}</pre></article>`;
  }
  if (endpoint === "/api/signing/status") {
    return `<article class="data-card stack"><h3>Signing Readiness</h3><div class="card-row"><span class="pill">${data.signed ? "signed" : "unsigned"}</span><span>${data.notarized ? "notarized" : "not notarized"}</span></div><p>${escapeHtml(data.message || "")}</p><pre>${escapeHtml(JSON.stringify({ macos: data.macos, windows: data.windows, linux: data.linux }, null, 2))}</pre></article>`;
  }
  return renderCards(endpoint, [data]);
}

function renderPermissions(endpoint, data) {
  if (endpoint.endsWith("/rules")) return renderCards(endpoint, data.profiles || []);
  return `<article class="data-card"><h3>Active Mode: ${escapeHtml(data.mode)}</h3>${summaryRows(data)}<div class="row"><button data-permission="safe">Safe</button><button class="secondary" data-permission="developer">Developer</button><button class="secondary" data-permission="full_automation">Full Automation</button></div><pre>${escapeHtml(JSON.stringify(data.rules_json, null, 2))}</pre></article>`;
}

function renderDashboard(data) {
  const stats = [
    ["Agents", data.agents?.count ?? 0],
    ["Campaigns", data.campaigns?.count ?? 0],
    ["Pending approvals", data.approvals?.pending ?? 0],
    ["Image jobs", data.jobs?.image?.count ?? 0],
    ["Video jobs", data.jobs?.video?.count ?? 0],
    ["Automations", data.automations?.count ?? 0],
    ["Providers", data.providers?.configured_count ?? 0],
  ];
  return `<div class="stat-grid">${stats.map(([label, value]) => `<article class="stat"><span>${label}</span><strong>${value}</strong></article>`).join("")}</div>`;
}

function renderApprovals(rows) {
  if (!rows.length) return `<div class="state empty">No approvals yet. Campaign and email drafts will appear here.</div>`;
  return `<div class="data-grid">${rows
    .map((approval) => {
      const preview = approval.preview || {};
      const meta = preview.metadata || {};
      return `<article class="data-card approval">
        <div class="card-row"><span class="pill">${escapeHtml(approval.status)}</span><span>${escapeHtml(approval.action_type)}</span></div>
        <h3>${escapeHtml(meta.campaign_name || "Draft approval")}</h3>
        <p><strong>Platform:</strong> ${escapeHtml(approval.connector_id || preview.platform || "email")}</p>
        <p><strong>Agent:</strong> ${escapeHtml(meta.agent_slug || "local-mvp")}</p>
        <pre>${escapeHtml(preview.text || preview.body || JSON.stringify(preview, null, 2))}</pre>
        <div class="row">
          <button data-approval="${approval.id}" data-decision="approve" ${approval.status !== "pending" ? "disabled" : ""}>Approve</button>
          <button class="secondary" data-approval="${approval.id}" data-decision="reject" ${approval.status !== "pending" ? "disabled" : ""}>Reject</button>
        </div>
      </article>`;
    })
    .join("")}</div>`;
}

function renderCards(endpoint, rows) {
  if (!rows.length) return `<div class="state empty">${endpoint} has no records yet.</div>`;
  if (endpoint === "/api/telegram/drafts") return renderTelegramDrafts(rows);
  return `<h3>${endpoint}</h3><div class="data-grid">${rows
    .slice(0, 18)
    .map((row) => `<article class="data-card"><h3>${escapeHtml(row.name || row.campaign_name || row.display_name || row.provider || row.platform || row.slug || row.id || "Record")}</h3>${summaryRows(row)}<pre>${escapeHtml(JSON.stringify(row, null, 2))}</pre></article>`)
    .join("")}</div>`;
}

function renderConnectors(data) {
  const configured = data.configured || [];
  const availableSocial = data.available?.social || [];
  const availableMessaging = data.available?.messaging || [];
  return `<article class="data-card"><h3>Configured</h3>${configured.length ? summaryList(configured) : `<div class="state empty">No connectors configured yet.</div>`}</article>
  <article class="data-card"><h3>Available Messaging Connectors</h3>${summaryList(availableMessaging.map((row) => ({ name: row.display_name, status: row.status })))}</article>
  <article class="data-card"><h3>Available Social Connectors</h3>${summaryList(availableSocial.map((row) => ({ name: row.display_name, status: row.platform })))}</article>`;
}

function renderSocialConnectors(rows) {
  if (!rows.length) return `<div class="state empty">No social connectors yet.</div>`;
  return `<h3>Social Connectors</h3><div class="data-grid">${rows.map((row) => `<article class="data-card">
    <div class="card-row"><span class="pill">${escapeHtml(row.status)}</span><span>${escapeHtml(row.platform)}</span><span>${row.auto_publish_enabled ? "Auto publish on" : "Auto publish off"}</span></div>
    <h3>${escapeHtml(row.platform === "x" ? "X / Twitter" : "LinkedIn")}</h3>
    <p><strong>Account:</strong> ${escapeHtml(row.account_name || "-")}</p>
    <p><strong>Scopes:</strong> ${escapeHtml((row.scopes || []).join(", ") || "-")}</p>
    <p><strong>Publish capability:</strong> ${escapeHtml(row.publish_capability || "unknown")}</p>
    <p><strong>Manual publish:</strong> ${row.manual_publish_enabled ? "Enabled" : "Disabled by default"}</p>
    <p><strong>Note:</strong> ${escapeHtml(row.notes || "Official API access required.")}</p>
    <pre>${escapeHtml(JSON.stringify(row.setup_instructions || [], null, 2))}</pre>
    <div class="row">
      <button data-social-connector="${escapeHtml(row.platform)}" data-social-action="setup">Setup</button>
      <button class="secondary" data-social-connector="${escapeHtml(row.platform)}" data-social-action="oauth-url">OAuth URL</button>
      <button class="secondary" data-social-connector="${escapeHtml(row.platform)}" data-social-action="test">Test</button>
      <button class="secondary" data-social-connector="${escapeHtml(row.platform)}" data-social-action="enable-publish">Enable Manual Publish</button>
      <button class="secondary" data-social-connector="${escapeHtml(row.platform)}" data-social-action="disable-publish">Disable Publish</button>
      <button class="secondary" data-social-connector="${escapeHtml(row.platform)}" data-social-action="disconnect">Disconnect</button>
    </div>
  </article>`).join("")}</div>`;
}

function renderSocialDrafts(rows) {
  if (!rows.length) return `<div class="state empty">No social drafts yet.</div>`;
  return `<h3>Social Drafts</h3><div class="data-grid">${rows.map((row) => `<article class="data-card">
    <div class="card-row"><span class="pill">${escapeHtml(row.status || "draft")}</span><span>${escapeHtml(row.platform)}</span><span>${escapeHtml(row.publish_status || "draft")}</span></div>
    <h3>${escapeHtml((row.metadata || {}).campaign_name || "Draft")}</h3>
    <pre>${escapeHtml(row.text || "")}</pre>
    <p><strong>Approval:</strong> ${escapeHtml(row.approval_id || "-")}</p>
    <p><strong>Connector:</strong> ${escapeHtml(row.connector_id || row.platform || "-")}</p>
    <p><strong>External post:</strong> ${escapeHtml(row.external_post_id || "-")}</p>
    ${row.publish_error ? `<p><strong>Blocked/error:</strong> ${escapeHtml(row.publish_error)}</p>` : ""}
    <div class="row">
      <button data-social-draft="${escapeHtml(row.id)}" data-social-draft-action="approve" ${row.status === "approved" || row.status === "published" ? "disabled" : ""}>Approve</button>
      <button class="secondary" data-social-draft="${escapeHtml(row.id)}" data-social-draft-action="publish-approved" data-social-platform="${escapeHtml(row.platform)}" ${row.status !== "approved" ? "disabled" : ""}>Publish Approved</button>
    </div>
  </article>`).join("")}</div>`;
}

function renderTelegramStatus(data) {
  return `<article class="data-card">
    <div class="card-row"><span class="pill">${escapeHtml(data.status)}</span><span>${data.enabled ? "Enabled" : "Disabled"}</span><span>Approval required</span></div>
    <h3>Telegram Bot</h3>
    <p><strong>Bot:</strong> ${escapeHtml(data.bot_username || "-")}</p>
    <p><strong>Token:</strong> ${escapeHtml(data.bot_token_masked || "not set")}</p>
    <p><strong>Assigned agent:</strong> ${escapeHtml(data.assigned_agent_slug || "-")}</p>
    <p><strong>Manual send:</strong> ${data.manual_send_enabled ? "Enabled" : "Disabled by default"}</p>
    <p><strong>Webhook:</strong> ${escapeHtml(data.webhook_url || "-")}</p>
    <pre>${escapeHtml(JSON.stringify(data.setup_instructions || [], null, 2))}</pre>
    <div class="row">
      <button data-telegram-action="setup">Setup</button>
      <button class="secondary" data-telegram-action="test">Test</button>
      <button class="secondary" data-telegram-action="enable">Enable</button>
      <button class="secondary" data-telegram-action="disable">Disable</button>
      <button class="secondary" data-telegram-action="disconnect">Disconnect</button>
    </div>
  </article>`;
}

function renderTelegramDrafts(rows) {
  return `<h3>Telegram Reply Drafts</h3><div class="data-grid">${rows.map((row) => `<article class="data-card"><div class="card-row"><span class="pill">${escapeHtml(row.status)}</span><span>${escapeHtml(row.risk_level || "low")}</span></div><h3>Chat ${escapeHtml(row.chat_id)}</h3><pre>${escapeHtml(row.draft_text || "")}</pre>${row.warning ? `<p><strong>Warning:</strong> ${escapeHtml(row.warning)}</p>` : ""}<div class="row"><button data-telegram-draft="${escapeHtml(row.id)}" data-telegram-decision="approve">Approve</button><button class="secondary" data-telegram-draft="${escapeHtml(row.id)}" data-telegram-decision="reject">Reject</button><button class="secondary" data-telegram-draft="${escapeHtml(row.id)}" data-telegram-decision="send-approved" ${row.status !== "approved" ? "disabled" : ""}>Send Approved</button></div></article>`).join("")}</div>`;
}

function summaryRows(row) {
  const keys = ["status", "platform", "provider", "agent_slug", "created_at", "output_path", "default_provider", "configured_count"];
  return keys.filter((key) => row[key]).map((key) => `<p><strong>${key}:</strong> ${escapeHtml(String(row[key]))}</p>`).join("");
}

function collectPlatforms(value) {
  return value.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean);
}

async function postJson(endpoint, body, successMessage, errorMessage, button) {
  if (button) button.disabled = true;
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    toast(response.ok ? successMessage : errorMessage, !response.ok);
    if (response.ok) loadLiveData();
  } catch (error) {
    toast(`${errorMessage}: ${String(error)}`, true);
  } finally {
    if (button) button.disabled = false;
  }
}

function summaryList(rows) {
  return `<ul>${rows.slice(0, 20).map((row) => `<li>${escapeHtml(row.name || row.display_name || row.provider || row.id)} <span>${escapeHtml(row.status || "")}</span></li>`).join("")}</ul>`;
}

function wireApprovalButtons() {
  document.querySelectorAll("[data-approval]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.approval;
      const decision = button.dataset.decision;
      button.disabled = true;
      const response = await fetch(`${API_BASE}/api/approvals/${id}/${decision}`, { method: "POST" });
      if (!response.ok) {
        toast(`Could not ${decision} approval`, true);
        button.disabled = false;
        return;
      }
      toast(`Approval ${decision}d`);
      loadLiveData();
    });
  });
}

function wireSettingsButtons() {
  document.querySelectorAll("[data-setting]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.setting;
      const value = document.querySelector(`[data-setting-value="${key}"]`)?.value || "";
      const response = await fetch(`${API_BASE}/api/settings/set`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ key, value }),
      });
      toast(response.ok ? "Setting saved" : "Could not save setting", !response.ok);
      if (response.ok) loadLiveData();
    });
  });
}

function wirePermissionButtons() {
  document.querySelectorAll("[data-permission]").forEach((button) => {
    button.addEventListener("click", async () => {
      const response = await fetch(`${API_BASE}/api/permissions/set`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ mode: button.dataset.permission }),
      });
      toast(response.ok ? "Permission mode updated" : "Could not update permission mode", !response.ok);
      if (response.ok) loadLiveData();
    });
  });
}

function wireImageGenerateButton() {
  const button = document.querySelector("#generate-image");
  if (!button || button.dataset.bound) return;
  button.dataset.bound = "true";
  button.addEventListener("click", async () => {
    const prompt = document.querySelector("#image-prompt")?.value?.trim();
    const mode = document.querySelector("#image-mode")?.value || "model_based";
    const provider = document.querySelector("#image-provider")?.value || "";
    const size = document.querySelector("#image-size")?.value || "1024x1024";
    const style = document.querySelector("#image-style")?.value || "clean editorial";
    const template = document.querySelector("#image-template")?.value || "";
    const platform = document.querySelector("#image-platform")?.value || "";
    const creativeType = document.querySelector("#image-creative-type")?.value || "";
    if (!prompt) {
      toast("Enter a prompt first", true);
      return;
    }
    button.disabled = true;
    try {
      const response = await fetch(`${API_BASE}/api/generation/image/generate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt, provider_name: provider, size, style, generation_mode: mode, template_name: template, platform, creative_type: creativeType }),
      });
      const data = response.ok ? await response.json() : {};
      const message = data.status === "completed" ? "Image generated" : data.status === "needs_provider_setup" ? "Prompt package created; provider setup needed" : data.status === "provider_error" ? "Provider error; prompt package saved" : "Image job created";
      toast(response.ok ? message : "Image generation failed", !response.ok || data.status === "provider_error");
      if (response.ok) loadLiveData();
    } finally {
      button.disabled = false;
    }
  });
}

function wireSocialCampaignForm() {
  const button = document.querySelector("#create-campaign");
  if (!button || button.dataset.bound) return;
  button.dataset.bound = "true";
  button.addEventListener("click", () => {
    const campaignName = document.querySelector("#campaign-name")?.value?.trim() || "UI Campaign";
    const project = document.querySelector("#campaign-project")?.value?.trim() || campaignName;
    const platforms = collectPlatforms(document.querySelector("#campaign-platforms")?.value || "instagram,linkedin,x,whatsapp");
    const goal = document.querySelector("#campaign-goal")?.value?.trim() || "Generate qualified leads";
    const days = Number(document.querySelector("#campaign-days")?.value || 7);
    postJson("/api/social/campaign/create", { campaign_name: campaignName, project, platforms, goal, days }, "Campaign created", "Could not create campaign", button);
  });
}

function wireAgentCreateForm() {
  const button = document.querySelector("#create-agent");
  if (!button || button.dataset.bound) return;
  button.dataset.bound = "true";
  button.addEventListener("click", () => {
    const name = document.querySelector("#agent-name")?.value?.trim();
    const role = document.querySelector("#agent-role")?.value?.trim() || "Custom Agent";
    const instructions = document.querySelector("#agent-instructions")?.value?.trim();
    if (!name || !instructions) return toast("Add agent name and instructions", true);
    const providerPreferences = {};
    const textProvider = document.querySelector("#agent-text-provider")?.value || "";
    const textModel = document.querySelector("#agent-text-model")?.value?.trim() || "";
    const imageProvider = document.querySelector("#agent-image-provider")?.value || "";
    const videoProvider = document.querySelector("#agent-video-provider")?.value || "";
    if (textProvider) providerPreferences.text_provider = textProvider;
    if (textModel) providerPreferences.text_model = textModel;
    if (imageProvider) providerPreferences.image_provider = imageProvider;
    if (videoProvider) providerPreferences.video_provider = videoProvider;
    postJson("/api/agents/create", { name, role, instructions, goal: instructions, provider_preferences: providerPreferences }, "Agent created", "Could not create agent", button);
  });
}

function wireEmailDraftForm() {
  const button = document.querySelector("#draft-email-reply");
  if (!button || button.dataset.bound) return;
  button.dataset.bound = "true";
  button.addEventListener("click", () => {
    const provider = document.querySelector("#email-provider")?.value || "gmail";
    const messageId = document.querySelector("#email-message-id")?.value?.trim() || "latest";
    const tone = document.querySelector("#email-tone")?.value?.trim() || "professional";
    const body = document.querySelector("#email-draft-body")?.value?.trim() || "";
    postJson("/api/email/draft-reply", { provider, message_id: messageId, tone, body }, "Email draft created, not sent", "Could not create email draft", button);
  });
  const actions = [
    ["#gmail-setup", "/api/email/gmail/setup", {}, "Gmail setup checked"],
    ["#gmail-test", "/api/email/gmail/test", {}, "Gmail tested"],
    ["#gmail-disconnect", "/api/email/gmail/disconnect", {}, "Gmail disconnected"],
  ];
  actions.forEach(([selector, endpoint, body, message]) => {
    const item = document.querySelector(selector);
    if (item && !item.dataset.bound) {
      item.dataset.bound = "true";
      item.addEventListener("click", () => postJson(endpoint, body, message, "Gmail action failed", item));
    }
  });
  const oauth = document.querySelector("#gmail-oauth");
  if (oauth && !oauth.dataset.bound) {
    oauth.dataset.bound = "true";
    oauth.addEventListener("click", async () => {
      const response = await fetch(`${API_BASE}/api/email/gmail/oauth/start`, { method: "POST" });
      const data = response.ok ? await response.json() : {};
      document.querySelector("#gmail-oauth-output").textContent = JSON.stringify(data, null, 2);
      toast(response.ok ? "OAuth URL ready" : "Could not create OAuth URL", !response.ok);
      if (response.ok) loadLiveData();
    });
  }
  const search = document.querySelector("#gmail-search");
  if (search && !search.dataset.bound) {
    search.dataset.bound = "true";
    search.addEventListener("click", () => postJson("/api/email/search", { provider: "gmail", query: document.querySelector("#email-query")?.value || "newer_than:7d", max_results: Number(document.querySelector("#email-max-results")?.value || 10) }, "Search completed", "Search failed", search));
  }
  const recent = document.querySelector("#gmail-recent");
  if (recent && !recent.dataset.bound) {
    recent.dataset.bound = "true";
    recent.addEventListener("click", () => postJson("/api/email/recent", { provider: "gmail", max_results: Number(document.querySelector("#email-max-results")?.value || 10) }, "Recent messages loaded", "Recent failed", recent));
  }
  const read = document.querySelector("#gmail-read");
  if (read && !read.dataset.bound) {
    read.dataset.bound = "true";
    read.addEventListener("click", () => postJson("/api/email/read", { provider: "gmail", message_id: document.querySelector("#email-message-id")?.value || "" }, "Message read", "Read failed", read));
  }
  const summarize = document.querySelector("#gmail-summarize");
  if (summarize && !summarize.dataset.bound) {
    summarize.dataset.bound = "true";
    summarize.addEventListener("click", () => postJson("/api/email/summarize", { provider: "gmail", message_id: document.querySelector("#email-message-id")?.value || "" }, "Message summarized", "Summarize failed", summarize));
  }
}

function wireAutomationForm() {
  const button = document.querySelector("#create-automation");
  if (!button || button.dataset.bound) return;
  button.dataset.bound = "true";
  button.addEventListener("click", () => {
    const name = document.querySelector("#automation-name")?.value?.trim() || "UI Automation";
    const agent = document.querySelector("#automation-agent")?.value || "automation-builder-agent";
    const trigger = document.querySelector("#automation-trigger")?.value || "manual";
    const time = document.querySelector("#automation-time")?.value || "09:00";
    const day = document.querySelector("#automation-day")?.value || "monday";
    const minutes = Number(document.querySelector("#automation-minutes")?.value || 60);
    const task = document.querySelector("#automation-task")?.value?.trim();
    if (!task) return toast("Add an automation task", true);
    if (trigger === "daily") return postJson("/api/automations/create-daily", { name, agent_slug: agent, time_of_day: time, task_prompt: task }, "Automation created", "Could not create automation", button);
    if (trigger === "weekly") return postJson("/api/automations/create-weekly", { name, agent_slug: agent, day, time_of_day: time, task_prompt: task }, "Automation created", "Could not create automation", button);
    if (trigger === "interval") return postJson("/api/automations/create-interval", { name, agent_slug: agent, minutes, task_prompt: task }, "Automation created", "Could not create automation", button);
    postJson("/api/automations/create", { name, agent_slug: agent, trigger_type: trigger, schedule_text: trigger, task_prompt: task }, "Automation created", "Could not create automation", button);
  });
  document.querySelectorAll("[data-scheduler-action]").forEach((item) => {
    if (item.dataset.bound) return;
    item.dataset.bound = "true";
    item.addEventListener("click", () => postJson(`/api/scheduler/${item.dataset.schedulerAction}`, {}, "Scheduler action completed", "Scheduler action failed", item));
  });
  document.querySelectorAll("[data-automation-run]").forEach((item) => {
    if (item.dataset.bound) return;
    item.dataset.bound = "true";
    item.addEventListener("click", () => postJson(`/api/automations/${item.dataset.automationRun}/run`, {}, "Automation run recorded", "Could not run automation", item));
  });
  document.querySelectorAll("[data-automation-toggle]").forEach((item) => {
    if (item.dataset.bound) return;
    item.dataset.bound = "true";
    item.addEventListener("click", () => postJson(`/api/automations/${item.dataset.automationToggle}/${item.dataset.enabled === "true" ? "enable" : "disable"}`, {}, "Automation updated", "Could not update automation", item));
  });
}

function wireSkillButtons() {
  document.querySelectorAll("[data-skill-action]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => postJson(`/api/skills/${button.dataset.skillAction}`, { skill_name: button.dataset.skill }, "Skill updated", "Could not update skill", button));
  });
}

function wireWorkspaceButtons() {
  const create = document.querySelector("#create-workspace");
  if (create && !create.dataset.bound) {
    create.dataset.bound = "true";
    create.addEventListener("click", () => {
      const name = document.querySelector("#workspace-name")?.value?.trim();
      if (!name) return toast("Add a workspace name", true);
      postJson("/api/workspaces/create", { name }, "Workspace created", "Could not create workspace", create);
    });
  }
  document.querySelectorAll("[data-workspace-default]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => postJson("/api/workspaces/default", { name: button.dataset.workspaceDefault }, "Default workspace updated", "Could not update workspace", button));
  });
}

function wireProviderButtons() {
  document.querySelectorAll("[data-provider-test]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const response = await fetch(`${API_BASE}/api/providers/${button.dataset.providerTest}/test`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({}),
        });
        const data = response.ok ? await response.json() : {};
        toast(data.success ? "Provider configuration found" : data.message || "Provider key missing", !data.success);
        if (response.ok) loadLiveData();
      } catch (error) {
        toast(`Could not test provider: ${String(error)}`, true);
      } finally {
        button.disabled = false;
      }
    });
  });
  document.querySelectorAll("[data-provider-default]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => postJson("/api/providers/default", { category: button.dataset.providerCategory || "text", provider_name: button.dataset.providerDefault }, "Default provider updated", "Could not set default provider", button));
  });
  document.querySelectorAll("[data-provider-toggle]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    const action = button.dataset.enabled === "true" ? "enable" : "disable";
    button.addEventListener("click", () => postJson(`/api/providers/${button.dataset.providerToggle}/${action}`, {}, "Provider updated", "Could not update provider", button));
  });
  document.querySelectorAll("[data-provider-fallback]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => postJson("/api/providers/fallback", { category: button.dataset.providerCategory || "text", provider_name: button.dataset.providerFallback }, "Fallback provider updated", "Could not set fallback provider", button));
  });
  const saveCustom = document.querySelector("#save-custom-provider");
  if (saveCustom && !saveCustom.dataset.bound) {
    saveCustom.dataset.bound = "true";
    saveCustom.addEventListener("click", () => {
      const name = document.querySelector("#custom-provider-name")?.value?.trim();
      if (!name) return toast("Add a provider name", true);
      postJson("/api/providers/setup", {
        name,
        display_name: document.querySelector("#custom-provider-display")?.value?.trim() || name,
        category: document.querySelector("#custom-provider-category")?.value || "text",
        provider_type: document.querySelector("#custom-provider-type")?.value || "custom_openai_compatible",
        base_url: document.querySelector("#custom-provider-base-url")?.value?.trim() || "",
        api_key_env: document.querySelector("#custom-provider-api-env")?.value?.trim() || "",
        default_model: document.querySelector("#custom-provider-model")?.value?.trim() || "",
      }, "Custom provider saved", "Could not save custom provider", saveCustom);
    });
  }
  document.querySelectorAll("[data-provider-generate-test]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const response = await fetch(`${API_BASE}/api/text/generate`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ prompt: "Say hello from Liuant Agentic OS in one sentence.", provider_name: button.dataset.providerGenerateTest, model: button.dataset.providerModel || undefined, max_tokens: 80 }),
        });
        const data = response.ok ? await response.json() : {};
        toast(data.status === "completed" ? `Generated: ${data.text}` : data.error || data.status || "Text generation unavailable", data.status !== "completed");
      } catch (error) {
        toast(`Could not generate test text: ${String(error)}`, true);
      } finally {
        button.disabled = false;
      }
    });
  });
}

function wireAgentRunForm() {
  const button = document.querySelector("#run-agent");
  if (!button || button.dataset.bound) return;
  button.dataset.bound = "true";
  button.addEventListener("click", () => {
    const agentSlug = document.querySelector("#run-agent-slug")?.value?.trim() || "marketing-agent";
    const prompt = document.querySelector("#run-agent-prompt")?.value?.trim();
    if (!prompt) return toast("Add an agent task", true);
    postJson("/api/agents/run", {
      agent_slug: agentSlug,
      prompt,
      ai_enhancement: document.querySelector("#run-agent-ai")?.checked || false,
      provider_name: document.querySelector("#run-agent-provider")?.value || "",
      model: document.querySelector("#run-agent-model")?.value?.trim() || "",
    }, "Agent run created", "Could not run agent", button);
  });
}

function wireTelegramButtons() {
  document.querySelectorAll("[data-telegram-action]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    const action = button.dataset.telegramAction;
    button.addEventListener("click", () => postJson(`/api/telegram/${action}`, {}, `Telegram ${action} completed`, `Telegram ${action} failed`, button));
  });
  document.querySelectorAll("[data-telegram-draft]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    const id = button.dataset.telegramDraft;
    const decision = button.dataset.telegramDecision;
    button.addEventListener("click", () => postJson(`/api/telegram/drafts/${id}/${decision}`, {}, "Telegram draft updated", "Could not update Telegram draft", button));
  });
}

function wireSocialConnectorButtons() {
  document.querySelectorAll("[data-social-connector]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    const platform = button.dataset.socialConnector;
    const action = button.dataset.socialAction;
    button.addEventListener("click", async () => {
      if (action === "oauth-url") {
        const response = await fetch(`${API_BASE}/api/social/${platform}/oauth/start`, { method: "POST" });
        const data = response.ok ? await response.json() : {};
        toast(response.ok ? "OAuth URL ready. Open it from the live data preview." : "Could not create OAuth URL", !response.ok);
        if (response.ok) {
          console.log(data);
          loadLiveData();
        }
        return;
      }
      if (action === "enable-publish" || action === "disable-publish") {
        const endpointAction = action === "enable-publish" ? "enable-publish" : "disable-publish";
        postJson(`/api/social/connectors/${platform}/${endpointAction}`, {}, "Social connector updated", "Could not update social connector", button);
        return;
      }
      postJson(`/api/social/${platform}/${action}`, {}, `Social ${action} completed`, `Social ${action} failed`, button);
    });
  });
}

function wireSocialDraftButtons() {
  document.querySelectorAll("[data-social-draft]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    const draftId = button.dataset.socialDraft;
    const action = button.dataset.socialDraftAction;
    button.addEventListener("click", () => {
      if (action === "approve") {
        postJson(`/api/social/drafts/${draftId}/approve`, {}, "Social draft approved", "Could not approve social draft", button);
        return;
      }
      postJson(`/api/social/drafts/${draftId}/publish-approved`, { connector_id: button.dataset.socialPlatform }, "Publish attempt completed", "Publish attempt failed", button);
    });
  });
}

function wireMemoryButtons() {
  const add = document.querySelector("#add-memory");
  if (add && !add.dataset.bound) {
    add.dataset.bound = "true";
    add.addEventListener("click", () => postJson("/api/memory/add", { content: document.querySelector("#memory-content")?.value || "", memory_type: document.querySelector("#memory-type")?.value || "user" }, "Memory added", "Could not add memory", add));
  }
  const search = document.querySelector("#search-memory");
  if (search && !search.dataset.bound) {
    search.dataset.bound = "true";
    search.addEventListener("click", () => postJson("/api/memory/search", { query: document.querySelector("#memory-query")?.value || "" }, "Memory search completed", "Memory search failed", search));
  }
}

function wireKnowledgeButtons() {
  const add = document.querySelector("#add-knowledge");
  if (add && !add.dataset.bound) {
    add.dataset.bound = "true";
    add.addEventListener("click", () => postJson("/api/knowledge/add-text", { text: document.querySelector("#knowledge-text")?.value || "", title: "UI Knowledge" }, "Knowledge added", "Could not add knowledge", add));
  }
  const indexFile = document.querySelector("#index-knowledge-file");
  if (indexFile && !indexFile.dataset.bound) {
    indexFile.dataset.bound = "true";
    indexFile.addEventListener("click", () => postJson("/api/knowledge/index-file", { path: document.querySelector("#knowledge-file")?.value || "" }, "File indexed", "Could not index file", indexFile));
  }
  const search = document.querySelector("#search-knowledge");
  if (search && !search.dataset.bound) {
    search.dataset.bound = "true";
    search.addEventListener("click", async () => {
      const response = await fetch(`${API_BASE}/api/knowledge/search`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: document.querySelector("#knowledge-query")?.value || "" }) });
      const data = response.ok ? await response.json() : {};
      const output = document.querySelector("#knowledge-output");
      if (output) output.textContent = JSON.stringify(data, null, 2);
      toast(response.ok ? "Knowledge search completed" : "Knowledge search failed", !response.ok);
    });
  }
}

function wireVideoButtons() {
  const generate = document.querySelector("#generate-video");
  const storyboard = document.querySelector("#storyboard-video");
  [generate, storyboard].forEach((button) => {
    if (!button || button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      const prompt = document.querySelector("#video-prompt")?.value?.trim();
      if (!prompt) {
        toast("Enter a prompt first", true);
        return;
      }
      button.disabled = true;
      const body = collectVideoPayload(prompt);
      const endpoint = button.id === "storyboard-video" ? "/api/generation/video/storyboard" : "/api/generation/video/generate";
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      button.disabled = false;
      toast(response.ok ? "Video job created" : "Video job failed", !response.ok);
      if (response.ok) loadLiveData();
    });
  });
  document.querySelectorAll("[data-video-action]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      const action = button.dataset.videoAction;
      const jobId = button.dataset.job;
      const method = action === "export" ? "GET" : "POST";
      const response = await fetch(`${API_BASE}/api/generation/video/jobs/${jobId}/${action}`, { method });
      toast(response.ok ? `Video ${action} completed` : `Video ${action} failed`, !response.ok);
      if (response.ok) loadLiveData();
    });
  });
}

function wireVerificationButtons() {
  document.querySelectorAll("[data-verify]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", async () => {
      const target = button.dataset.verify;
      const response = await fetch(`${API_BASE}/api/verify/${target}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({}) });
      toast(response.ok ? "Verification completed" : "Verification failed", !response.ok);
      if (response.ok) loadLiveData();
    });
  });
  document.querySelectorAll("[data-secret-action]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => postJson(`/api/secrets/${button.dataset.secretAction}`, {}, "Secret action completed", "Secret action failed", button));
  });
  document.querySelectorAll("[data-auth-action]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => postJson(`/api/auth/${button.dataset.authAction}`, {}, "Auth action completed", "Auth action failed", button));
  });
  document.querySelectorAll("[data-backup-action]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => postJson("/api/backup/create", {}, "Backup created", "Backup failed", button));
  });
}

function wireReleaseButtons() {
  document.querySelectorAll("[data-release-action]").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const action = button.dataset.releaseAction;
      const endpoint = action === "release-check" ? "/api/release/check" : action === "desktop-check" ? "/api/desktop/check" : "/api/signing/check";
      postJson(endpoint, { skip_tests: true }, "Release check completed", "Release check failed", button);
    });
  });
}

function collectVideoPayload(prompt) {
  return {
    prompt,
    topic: prompt,
    provider_name: document.querySelector("#video-provider")?.value || "",
    model: document.querySelector("#video-model")?.value || "",
    generation_mode: document.querySelector("#video-mode")?.value || "model_based",
    duration_seconds: Number(document.querySelector("#video-duration")?.value || 30),
    aspect_ratio: document.querySelector("#video-aspect-ratio")?.value || "9:16",
    resolution: document.querySelector("#video-resolution")?.value || "720p",
    style: document.querySelector("#video-style")?.value || "modern social video",
    template_name: document.querySelector("#video-template")?.value || "",
    platform: document.querySelector("#video-platform")?.value || "",
    scene_count: Number(document.querySelector("#video-scene-count")?.value || 4),
  };
}

function wireModeToggles() {
  document.querySelectorAll(".mode-toggle").forEach((button) => {
    if (button.dataset.bound) return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const target = document.querySelector(`#${button.dataset.modeTarget}`);
      if (!target) return;
      target.value = button.dataset.modeValue;
      document.querySelectorAll(`[data-mode-target="${button.dataset.modeTarget}"]`).forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll("[data-mode-panel]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.modePanel !== target.value));
    });
  });
}

function toast(message, isError = false) {
  let node = document.querySelector(".toast");
  if (!node) {
    node = document.createElement("div");
    node.className = "toast";
    document.body.appendChild(node);
  }
  node.textContent = message;
  node.classList.toggle("error", isError);
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2200);
}

function title(value) {
  return value.split("-").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function wireWorkflowSettings() {
  const showResult = (title, data) => {
    const panel = document.getElementById("workflow-panel-output");
    const titleNode = document.getElementById("output-title");
    const contentNode = document.getElementById("output-content");
    if (!panel || !titleNode || !contentNode) return;
    
    titleNode.textContent = title;
    contentNode.textContent = JSON.stringify(data, null, 2);
    panel.classList.remove("hidden");
  };

  const bindClick = (btnId, callback) => {
    const btn = document.getElementById(btnId);
    if (btn && !btn.dataset.bound) {
      btn.dataset.bound = "true";
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          await callback(btn);
        } catch (e) {
          toast(String(e), true);
        } finally {
          btn.disabled = false;
        }
      });
    }
  };

  // Workflow Management
  bindClick("btn-export-wf", async () => {
    const wfId = document.getElementById("export-wf-id")?.value?.trim();
    const outPath = document.getElementById("export-wf-path")?.value?.trim();
    if (!wfId || !outPath) return toast("Workflow ID and Output Path required", true);

    const res = await fetch(`${API_BASE}/api/skills/workflows/${wfId}/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ output_path: outPath })
    });
    const data = await res.json();
    showResult("Export Workflow Result", data);
    toast(res.ok && data.status !== "error" ? "Workflow exported successfully" : "Export failed", !res.ok || data.status === "error");
  });

  bindClick("btn-import-wf", async () => {
    const archivePath = document.getElementById("import-wf-path")?.value?.trim();
    const confirm = document.getElementById("import-wf-confirm")?.checked || false;
    if (!archivePath) return toast("Archive Path required", true);

    const res = await fetch(`${API_BASE}/api/skills/workflows/import`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ archive_path: archivePath, confirm })
    });
    const data = await res.json();
    showResult("Import Workflow Result", data);
    toast(res.ok && data.status === "imported" ? "Workflow imported successfully" : (data.message || "Import failed"), !res.ok || data.status !== "imported");
  });

  bindClick("btn-validate-wf", async () => {
    const archivePath = document.getElementById("validate-wf-path")?.value?.trim();
    if (!archivePath) return toast("Archive Path required", true);

    const res = await fetch(`${API_BASE}/api/skills/workflows/validate-file`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ archive_path: archivePath })
    });
    const data = await res.json();
    showResult("Validate Package Result", data);
    toast(res.ok && data.status !== "failed" ? "Validation passed" : "Validation failed", !res.ok || data.status === "failed");
  });

  // Workflow Packs
  bindClick("btn-export-pack", async () => {
    const idsText = document.getElementById("pack-wf-ids")?.value?.trim();
    const packId = document.getElementById("pack-id")?.value?.trim();
    const outPath = document.getElementById("pack-path")?.value?.trim();
    const name = document.getElementById("pack-name")?.value?.trim();
    const version = document.getElementById("pack-version")?.value?.trim();
    
    if (!packId || !outPath) return toast("Pack ID and Output Path required", true);
    const workflowIds = idsText ? idsText.split(",").map(s => s.trim()).filter(Boolean) : [];

    const res = await fetch(`${API_BASE}/api/skills/workflows/packs/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        workflow_ids: workflowIds,
        pack_id: packId,
        output_path: outPath,
        metadata: { name, version }
      })
    });
    const data = await res.json();
    showResult("Export Pack Result", data);
    toast(res.ok && data.status !== "error" ? "Pack exported successfully" : "Export failed", !res.ok || data.status === "error");
  });

  bindClick("btn-import-pack", async () => {
    const archivePath = document.getElementById("import-pack-path")?.value?.trim();
    const confirm = document.getElementById("import-pack-confirm")?.checked || false;
    if (!archivePath) return toast("Archive Path required", true);

    const res = await fetch(`${API_BASE}/api/skills/workflows/packs/import`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ archive_path: archivePath, confirm })
    });
    const data = await res.json();
    showResult("Import Pack Result", data);
    toast(res.ok && data.status === "imported" ? "Pack imported successfully" : (data.message || "Import failed"), !res.ok || data.status !== "imported");
  });

  bindClick("btn-inspect-pack", async () => {
    const archivePath = document.getElementById("inspect-pack-path")?.value?.trim();
    if (!archivePath) return toast("Archive Path required", true);

    const res = await fetch(`${API_BASE}/api/skills/workflows/packs/inspect`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ archive_path: archivePath })
    });
    const data = await res.json();
    showResult("Inspect Pack Result", data);
    toast(res.ok && data.status === "ok" ? "Pack inspected successfully" : "Inspection failed", !res.ok || data.status !== "ok");
  });

  // Backup & Restore
  bindClick("btn-val-backup", async () => {
    const path = document.getElementById("val-backup-path")?.value?.trim();
    if (!path) return toast("Backup file path required", true);

    const res = await fetch(`${API_BASE}/api/backup/validate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ file_path: path })
    });
    const data = await res.json();
    showResult("Validate Backup Result", data);
    toast(res.ok && data.status !== "failed" ? "Backup validation passed" : "Backup validation failed", !res.ok || data.status === "failed");
  });

  bindClick("btn-inspect-backup", async () => {
    const path = document.getElementById("inspect-backup-path")?.value?.trim();
    if (!path) return toast("Backup file path required", true);

    const res = await fetch(`${API_BASE}/api/backup/inspect`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ file_path: path })
    });
    const data = await res.json();
    showResult("Inspect Backup Result", data);
    toast(res.ok && data.status === "ok" ? "Backup inspected successfully" : "Inspection failed", !res.ok || data.status !== "ok");
  });

  bindClick("btn-restore-backup", async () => {
    const path = document.getElementById("restore-backup-path")?.value?.trim();
    const confirm = document.getElementById("restore-backup-confirm")?.checked || false;
    if (!path) return toast("Backup file path required", true);

    const res = await fetch(`${API_BASE}/api/backup/restore`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ file_path: path, confirm })
    });
    const data = await res.json();
    showResult("Restore Backup Result", data);
    toast(res.ok && data.status === "restored" ? "Backup restored successfully" : (data.message || "Restore failed"), !res.ok || data.status !== "restored");
  });
}

loadLiveData();
