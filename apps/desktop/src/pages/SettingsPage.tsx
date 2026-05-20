import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";

type SettingsSection = {
  id: string;
  label: string;
};

const SECTIONS: SettingsSection[] = [
  { id: "general", label: "General" },
  { id: "providers", label: "Models & Providers" },
  { id: "model-roles", label: "Model Roles" },
  { id: "connectors", label: "Connectors" },
  { id: "agents", label: "Agents" },
  { id: "automations", label: "Automations" },
  { id: "skills", label: "Skills" },
  { id: "workflows", label: "Workflows" },
  { id: "usage", label: "Usage & Budgeting" },
  { id: "memory", label: "Memory & Knowledge" },
  { id: "security", label: "Security" },
  { id: "backend", label: "Desktop & Backend" },
  { id: "voice", label: "Voice Assistant" },
  { id: "browser", label: "Browser & Desktop" },
  { id: "release", label: "Release & Updates" },
];

const SECTION_HELP: Record<string, string> = {
  general: "App version, workspace path, permission mode, and local auth settings.",
  providers: "Configure AI providers and set default models for text, image, video, and embeddings.",
  "model-roles": "Assign specific models to roles (Thinking, Coding, Planning). Configure Discussion Mode for multi-model collaboration.",
  connectors: "Connected external services. Use Chat to add Gmail, Telegram, LinkedIn, or X.",
  agents: "AI agents that perform tasks. Create and manage agents from here or through Chat.",
  automations: "Scheduled tasks that run agents on a recurring basis. Create and manage from Chat.",
  skills: "Installed skills extend Liuant's capabilities. Browse and install from Chat.",
  workflows: "Workflow templates, preview, permissions review, dry-run, execution, audit history, URL staging, lint fixes, and recommendations.",
  usage: "Configure daily and monthly cost limits, monitor budget status, and export detailed usage logs.",
  memory: "Saved facts and preferences that Liuant remembers. Say 'remember...' in Chat to add.",
  security: "API tokens, secret store status, and audit commands. Handle with care.",
  backend: "Backend connection mode, URL, and managed process controls.",
  voice: "Configure assistant wake name, STT/TTS providers, speech options, and transcript logging.",
  browser: "Browser automation toggles, Search Providers, and Desktop App automation safety.",
  release: "Version info, build status, signing status, and release artifacts.",
};

export function SettingsPage() {
  const [activeSection, setActiveSection] = useState("general");
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Array<{ key: string; value: string }>>("/api/settings")
      .then((data) => {
        const map: Record<string, string> = {};
        for (const item of data) map[item.key] = item.value;
        setSettings(map);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const section = useMemo(() => SECTIONS.find((s) => s.id === activeSection) || SECTIONS[0], [activeSection]);

  if (loading) return <LoadingSpinner label="Loading settings..." />;

  return (
    <div className="settings-layout">
      <nav className="settings-nav">
        {SECTIONS.map((s) => (
          <button key={s.id} className={s.id === activeSection ? "active" : ""} onClick={() => setActiveSection(s.id)}>
            {s.label}
          </button>
        ))}
      </nav>
      <div className="settings-content">
        <h3>{section.label}</h3>
        <p className="setting-helper">{SECTION_HELP[section.id] || ""}</p>
        <div className="settings-panel">
          {activeSection === "general" && <GeneralSettings settings={settings} />}
          {activeSection === "providers" && <ProvidersSettings />}
          {activeSection === "model-roles" && <ModelRolesSettings />}
          {activeSection === "connectors" && <ConnectorsSettings />}
          {activeSection === "agents" && <AgentsSettings />}
          {activeSection === "automations" && <AutomationsSettings />}
          {activeSection === "skills" && <SkillsSettings />}
          {activeSection === "workflows" && <WorkflowSettings />}
          {activeSection === "usage" && <UsageSettings />}
          {activeSection === "memory" && <MemorySettings />}
          {activeSection === "security" && <SecuritySettings />}
          {activeSection === "backend" && <BackendSettings settings={settings} />}
          {activeSection === "voice" && <VoiceSettings />}
          {activeSection === "browser" && <BrowserAutomationSettings />}
          {activeSection === "release" && <ReleaseSettings />}
        </div>
      </div>
    </div>
  );
}

function GeneralSettings({ settings }: { settings: Record<string, string> }) {
  return (
    <div className="settings-section">
      <div className="setting-row"><span className="setting-label">App Version</span><span className="setting-value">{settings.app_version || "0.7.1"}</span></div>
      <div className="setting-row"><span className="setting-label">Environment</span><span className="setting-value">{settings.app_environment || "local"}</span></div>
      <div className="setting-row"><span className="setting-label">Default Workspace</span><span className="setting-value">{settings.default_workspace || "default"}</span></div>
      <div className="setting-row"><span className="setting-label">Workspace Path</span><span className="setting-value mono">{settings.export_root || "workspace/"}</span></div>
      <div className="setting-row"><span className="setting-label">Permission Mode</span><span className="setting-value">{settings.permission_mode || "safe"}</span></div>
      <div className="setting-row"><span className="setting-label">Local Auth</span><span className="setting-value">{settings.local_auth_enabled === "true" ? "Enabled" : "Disabled"}</span></div>
      <div className="setting-row"><span className="setting-label">Telemetry</span><span className="setting-value">{settings.telemetry_enabled === "true" ? "Enabled" : "Disabled"}</span></div>
      <div className="setting-row"><span className="setting-label">Debug Mode</span><span className="setting-value">{settings.debug_mode === "true" ? "Enabled" : "Disabled"}</span></div>
    </div>
  );
}

function ProvidersSettings() {
  const [providers, setProviders] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/providers/status").then(setProviders).catch(() => {});
  }, []);
  if (!providers) return <LoadingSpinner label="Loading providers..." />;
  const providerList = (providers.providers as Array<Record<string, unknown>>) || [];
  return (
    <div className="settings-section">
      <div className="setting-row"><span className="setting-label">Default Provider</span><span className="setting-value">{String(providers.default_provider || "none")}</span></div>
      <div className="setting-row"><span className="setting-label">Configured</span><span className="setting-value">{String(providers.configured_count || 0)} of {String(providers.provider_count || 0)}</span></div>
      <h4>Configured Providers</h4>
      {providerList.length === 0 && <p className="setting-empty">No providers configured. Use Chat to set one up.</p>}
      {providerList.map((p) => (
        <div key={String(p.id)} className="setting-row">
          <span className="setting-label">{String(p.name || p.id)}</span>
          <span className={`setting-value ${String(p.status) === "configured" ? "status-good" : "status-warn"}`}>{String(p.status)}</span>
        </div>
      ))}
    </div>
  );
}

function ConnectorsSettings() {
  const [connectors, setConnectors] = useState<Array<Record<string, unknown>> | null>(null);
  useEffect(() => {
    apiGet<{ configured: Array<Record<string, unknown>> }>("/api/connectors").then((d) => setConnectors(d.configured || [])).catch(() => {});
  }, []);
  const list = connectors || [];
  return (
    <div className="settings-section">
      <h4>Connected Connectors</h4>
      {list.length === 0 && <p className="setting-empty">No connectors configured. Use Chat to connect Gmail, Telegram, or social accounts.</p>}
      {list.map((c) => (
        <div key={String(c.id || c.provider)} className="setting-row">
          <span className="setting-label">{String(c.provider || c.name)}</span>
          <span className={`setting-value ${String(c.status) === "connected" ? "status-good" : "status-warn"}`}>{String(c.status)}</span>
        </div>
      ))}
      <h4>Available Connectors</h4>
      <div className="setting-row"><span className="setting-label">Gmail</span><span className="setting-value">draft-only email</span></div>
      <div className="setting-row"><span className="setting-label">Telegram</span><span className="setting-value">draft-only messaging</span></div>
      <div className="setting-row"><span className="setting-label">LinkedIn</span><span className="setting-value">approval-gated publishing</span></div>
      <div className="setting-row"><span className="setting-label">X / Twitter</span><span className="setting-value">approval-gated publishing</span></div>
    </div>
  );
}

function AgentsSettings() {
  const [agents, setAgents] = useState<Array<Record<string, unknown>> | null>(null);
  useEffect(() => {
    apiGet<Array<Record<string, unknown>>>("/api/agents").then(setAgents).catch(() => {});
  }, []);
  const list = agents || [];
  return (
    <div className="settings-section">
      {list.length === 0 && <p className="setting-empty">No agents yet. Use Chat to create one.</p>}
      {list.map((a) => (
        <div key={String(a.slug || a.id)} className="setting-row">
          <span className="setting-label">{String(a.name || a.slug)}</span>
          <span className="setting-value">
            <span className={String(a.enabled) === "true" || a.enabled === true ? "status-good" : "status-warn"}>
              {String(a.enabled) === "true" || a.enabled === true ? "enabled" : "disabled"}
            </span>
            <span className="setting-meta">{String(a.slug || "")}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function AutomationsSettings() {
  const [automations, setAutomations] = useState<Array<Record<string, unknown>> | null>(null);
  const [scheduler, setScheduler] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    apiGet<Array<Record<string, unknown>>>("/api/automations").then(setAutomations).catch(() => {});
    apiGet<Record<string, unknown>>("/api/scheduler/status").then(setScheduler).catch(() => {});
  }, []);
  return (
    <div className="settings-section">
      {scheduler && (
        <>
          <div className="setting-row"><span className="setting-label">Scheduler</span><span className="setting-value">{String(scheduler.status || "unknown")}</span></div>
          <div className="setting-row"><span className="setting-label">Running Automations</span><span className="setting-value">{String((automations || []).length)}</span></div>
        </>
      )}
      {(automations || []).length === 0 && <p className="setting-empty">No automations yet. Use Chat to create one.</p>}
      {(automations || []).map((a) => (
        <div key={String(a.id)} className="setting-row">
          <span className="setting-label">{String(a.name || a.id)}</span>
          <span className="setting-value">
            <span>{String(a.schedule_text || a.schedule || "")}</span>
            <span className={`setting-meta ${String(a.enabled) === "true" || a.enabled === true ? "status-good" : "status-warn"}`}>
              {String(a.enabled) === "true" || a.enabled === true ? "enabled" : "disabled"}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

function SkillsSettings() {
  const [installed, setInstalled] = useState<Array<Record<string, unknown>> | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  useEffect(() => {
    apiGet<Array<Record<string, unknown>>>("/api/skills/installed").then(setInstalled).catch(() => {});
  }, []);
  const list = installed || [];
  return (
    <div className="settings-section">
      <h4>Installed Skills</h4>
      {list.length === 0 && <p className="setting-empty">No skills installed. Use Chat to browse and install skills.</p>}
      {list.map((s) => (
        <div key={String(s.skill_name || s.id)} className="setting-row skill-card">
          <span className="setting-label">{String(s.title || s.skill_name)}</span>
          <span className={`setting-value ${s.enabled ? "status-good" : "status-warn"}`}>{s.enabled ? "enabled" : "disabled"}</span>
        </div>
      ))}

      <h4>Skill Search & Upgrade Panel</h4>
      <p className="setting-note">Search installed skills or plan upgrade parameters. Use Chat to install additional skill packs.</p>
      <div className="setting-row">
        <input 
          className="setting-input" 
          type="text" 
          placeholder="Search skills..." 
          value={searchQuery} 
          onChange={(e) => setSearchQuery(e.target.value)} 
        />
        <button className="setting-btn">Search</button>
      </div>
      <div className="setting-commands">
        <code>./liuant skills install hello-skill</code>
        <code>./liuant skills upgrade hello-skill</code>
      </div>
    </div>
  );
}

function MemorySettings() {
  const [memories, setMemories] = useState<Array<Record<string, unknown>> | null>(null);
  useEffect(() => {
    apiGet<Array<Record<string, unknown>>>("/api/memory").then(setMemories).catch(() => {});
  }, []);
  const list = memories || [];
  return (
    <div className="settings-section">
      <div className="setting-row"><span className="setting-label">Memories</span><span className="setting-value">{list.length}</span></div>
      {list.length === 0 && <p className="setting-empty">No memories yet. Say 'remember...' in Chat to save one.</p>}
      {list.slice(0, 10).map((m) => (
        <div key={String(m.id)} className="setting-row">
          <span className="setting-label">{String(m.type || "note")}</span>
          <span className="setting-value mono">{String(m.content || "").slice(0, 60)}</span>
        </div>
      ))}
    </div>
  );
}

function SecuritySettings() {
  const [secrets, setSecrets] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/secrets/status").then(setSecrets).catch(() => {});
  }, []);
  return (
    <div className="settings-section">
      <div className="setting-row"><span className="setting-label">Secret Backend</span><span className="setting-value">{String(secrets?.default_backend || "not checked")}</span></div>
      <div className="setting-row"><span className="setting-label">Secrets Count</span><span className="setting-value">{String(secrets?.count || secrets?.secret_count || 0)}</span></div>
      <div className="setting-row"><span className="setting-label">Backend Encrypted</span><span className="setting-value">{String(secrets?.encrypted || "unknown")}</span></div>
      <h4>Security Commands</h4>
      <div className="setting-commands">
        <code>./liuant auth status</code>
        <code>./liuant auth token</code>
        <code>./liuant secrets status</code>
        <code>./liuant secrets migrate</code>
        <code>./liuant security audit-secrets</code>
        <code>./liuant backup create</code>
      </div>
    </div>
  );
}

function BackendSettings({ settings }: { settings: Record<string, string> }) {
  const [backendStatus, setBackendStatus] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/desktop/backend-status").then(setBackendStatus).catch(() => {});
  }, []);
  const sc = (backendStatus as Record<string, unknown>)?.sidecar_status as string || "not_used";
  const scAvailable = (backendStatus as Record<string, unknown>)?.bundled_sidecar_available === true;
  return (
    <div className="settings-section">
      <div className="setting-row"><span className="setting-label">Backend Mode</span><span className="setting-value">{settings.desktop_backend_mode || "external_backend"}</span></div>
      <div className="setting-row"><span className="setting-label">Backend URL</span><span className="setting-value mono">{settings.desktop_backend_url || "http://127.0.0.1:8765"}</span></div>
      <div className="setting-row"><span className="setting-label">Auto Start</span><span className="setting-value">{settings.desktop_auto_start_backend === "true" ? "Enabled" : "Disabled"}</span></div>
      <h4>Commands</h4>
      <div className="setting-commands">
        <code>./liuant desktop backend-mode</code>
        <code>./liuant desktop backend-start</code>
        <code>./liuant desktop backend-stop</code>
        <code>./liuant desktop backend-status</code>
        <code>./liuant desktop first-run-check</code>
      </div>
      <h4>Backend Modes</h4>
      <div className="setting-row"><span className="setting-label">external_backend</span><span className="setting-value">Manual start (recommended)</span></div>
      <div className="setting-row"><span className="setting-label">managed_backend</span><span className="setting-value">CLI-managed local backend</span></div>
      <div className="setting-row"><span className={`setting-label`}>{scAvailable ? "" : "warn-label "}bundled_sidecar</span><span className={`setting-value ${scAvailable ? "status-good" : "status-warn"}`}>{scAvailable ? "Available" : sc === "pending" ? "Pending — build with ./liuant sidecar build" : "Not implemented"}</span></div>
      <h4>Sidecar</h4>
      <div className="setting-commands">
        <code>./liuant sidecar status</code>
        <code>./liuant sidecar build --confirm</code>
        <code>./liuant sidecar check</code>
        <code>./liuant sidecar run</code>
        <code>./liuant sidecar stop --confirm</code>
      </div>
    </div>
  );
}

function ReleaseSettings() {
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [signingStatus, setSigningStatus] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/release/desktop-report").then(setReport).catch(() => {});
    apiGet<Record<string, unknown>>("/api/signing/status").then(setSigningStatus).catch(() => {});
  }, []);
  const mac = (signingStatus?.macos as Record<string, unknown>) || {};
  const signReady = report && (report.signing_readiness as Record<string, unknown>)?.codesign_ready;
  const notarizeReady = report && (report.signing_readiness as Record<string, unknown>)?.notarize_ready;
  const devIdConfigured = mac.developer_id_configured === true;
  return (
    <div className="settings-section">
      <div className="setting-row"><span className="setting-label">App Version</span><span className="setting-value">0.9.0</span></div>
      <div className="setting-row"><span className="setting-label">Build Type</span><span className="setting-value">Community (unsigned)</span></div>
      <div className="setting-row"><span className="setting-label">License</span><span className="setting-value">MIT</span></div>
      <div className="setting-row"><span className="setting-label">Source</span><span className="setting-value">Open-source</span></div>
      <div className="setting-row"><span className="setting-label">Signed</span><span className="setting-value status-warn">false</span></div>
      <div className="setting-row"><span className="setting-label">Notarized</span><span className="setting-value status-warn">false</span></div>
      <h4>Signing Readiness (Maintainers Only)</h4>
      <div className="setting-row"><span className="setting-label">Codesign Ready</span><span className={`setting-value ${devIdConfigured ? "status-good" : "status-warn"}`}>{devIdConfigured ? "yes" : "no"}</span></div>
      <div className="setting-row"><span className="setting-label">Notarize Ready</span><span className={`setting-value ${notarizeReady ? "status-good" : "status-warn"}`}>{notarizeReady ? "yes" : "no"}</span></div>
      {!devIdConfigured && (
        <div className="signing-blocked">
          <p><strong>Signing blocked</strong> — Apple Developer ID not configured (optional — community builds are unsigned).</p>
          <p>Required environment variable:</p>
          <code className="blocked-env">APPLE_DEVELOPER_ID_APPLICATION</code>
          <p>Check available identities:</p>
          <code className="blocked-cmd">security find-identity -v -p codesigning</code>
          <p>Next step:</p>
          <code className="blocked-cmd">./liuant signing macos-preflight</code>
          <p className="signing-doc-link">See <code>docs/MACOS_SIGNING_NOTARIZATION.md</code> for the full maintainer guide.</p>
        </div>
      )}
      {report && (
        <>
          <div className="setting-row"><span className="setting-label">Frontend Build</span><span className="setting-value">{String(report.frontend_build_status || "unknown")}</span></div>
          <div className="setting-row"><span className="setting-label">Native Build</span><span className="setting-value">{String(report.native_build_status || "not run")}</span></div>
          <div className="setting-row"><span className="setting-label">Icon Status</span><span className="setting-value">{String((report.icon_status as Record<string, unknown>)?.status || "unknown")}</span></div>
        </>
      )}
      <h4>Signing Commands</h4>
      <div className="setting-commands">
        <code>./liuant signing status</code>
        <code>./liuant signing macos-status</code>
        <code>./liuant signing macos-preflight</code>
        <code>./liuant signing macos-sign --dry-run</code>
        <code>./liuant signing macos-notarize --dry-run</code>
      </div>
      <h4>Release Commands</h4>
      <div className="setting-commands">
        <code>./liuant release macos-qa</code>
        <code>./liuant release unsigned-build-check</code>
        <code>./liuant release verify-artifacts</code>
        <code>./liuant release manifest</code>
      </div>
      <p className="setting-note">The DMG is unsigned. macOS will show security warnings. See docs/MACOS_UNSIGNED_INSTALL_QA.md for install steps.</p>
    </div>
  );
}

function ModelRolesSettings() {
  const [roles, setRoles] = useState<Record<string, unknown> | null>(null);
  const [discussion, setDiscussion] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<Record<string, unknown>>("/api/models/roles").catch(() => null),
      apiGet<Record<string, unknown>>("/api/models/discussion").catch(() => null),
    ]).then(([r, d]) => {
      setRoles(r);
      setDiscussion(d);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingSpinner label="Loading model roles..." />;

  const roleDefs = (roles?.roles || {}) as Record<string, { provider: string; model: string }>;
  const disc = discussion || {};
  const roleLabels: Record<string, string> = {
    default: "Default Model",
    thinking: "Thinking Model",
    coding: "Coding Model",
    planning: "Planning Model",
    fast: "Fast Model (optional)",
    fallback: "Fallback Model (optional)",
  };
  const roleDescriptions: Record<string, string> = {
    default: "Used when no specific role is needed.",
    thinking: "Deep reasoning, analysis, strategy, reviews, architecture.",
    coding: "Code generation, debugging, refactoring, tests.",
    planning: "Roadmaps, task breakdowns, execution plans, timelines.",
    fast: "Quick summaries, simple chat, low-cost responses.",
    fallback: "Used if selected role model is unavailable.",
  };

  return (
    <div className="settings-section">
      <h4>Model Roles</h4>
      <p className="setting-note">Assign specific models to roles for better task-specific responses.</p>
      {Object.entries(roleLabels).map(([key, label]) => {
        const cfg = roleDefs[key] || { provider: "", model: "" };
        const provider = (cfg as any).provider || "";
        const model = (cfg as any).model || "";
        const isOptional = key === "fast" || key === "fallback";
        const isLocal = ["ollama", "lmstudio", "local_hash_embedding", "whisper_local", "piper_local", "coqui_local", "hyperframes_skill"].includes(provider.toLowerCase());
        const isCloud = provider ? !isLocal : false;
        return (
          <div key={key} className="setting-row">
            <span className="setting-label">
              {label}
              {isOptional && <span className="setting-optional"> (optional)</span>}
            </span>
            <span className="setting-value">
              {provider && model ? (
                <span>
                  <span className={isCloud ? "status-warn" : "status-good"}>
                    {provider}/{model}
                  </span>
                  {isCloud && <span className="cost-badge"> ☁️ cloud</span>}
                  {!isCloud && provider && <span className="local-badge"> 🖥️ local</span>}
                </span>
              ) : (
                <span className="status-warn">Not configured</span>
              )}
            </span>
          </div>
        );
      })}
      <h4>Discussion Mode</h4>
      <p className="setting-note">
        Discussion Mode lets multiple models collaborate on a response. Each model gives an independent answer, then reviews others, and a final model synthesizes the best response.
        <br />
        <strong>Warning:</strong> Discussion Mode uses multiple model calls per round. Cloud models will incur costs.
      </p>
      <div className="setting-row">
        <span className="setting-label">Enabled</span>
        <span className={`setting-value ${disc.discussion_mode_enabled === true ? "status-good" : "status-warn"}`}>
          {disc.discussion_mode_enabled === true ? "Yes" : "No (disabled by default)"}
        </span>
      </div>
      <div className="setting-row">
        <span className="setting-label">Default Rounds</span>
        <span className="setting-value">{String(disc.discussion_mode_default_rounds || 2)}</span>
      </div>
      <div className="setting-row">
        <span className="setting-label">Max Rounds</span>
        <span className="setting-value">{String(disc.discussion_mode_max_rounds || 4)}</span>
      </div>
      <div className="setting-row">
        <span className="setting-label">Final Judge Model</span>
        <span className="setting-value">{String(disc.discussion_mode_final_role || "thinking")}</span>
      </div>
      <h4>CLI Commands</h4>
      <div className="setting-commands">
        <code>./liuant models roles</code>
        <code>./liuant models role-set thinking --provider openrouter --model "deepseek/deepseek-reasoner"</code>
        <code>./liuant models role-set coding --provider openrouter --model "qwen/qwen3-coder"</code>
        <code>./liuant models role-test thinking</code>
        <code>./liuant models discussion-status</code>
      </div>
    </div>
  );
}


// ============================================================
// v2.6.0: Workflow Settings
// ============================================================

function WorkflowSettings() {
  const [workflows, setWorkflows] = useState<Array<Record<string, unknown>> | null>(null);
  const [auditLogs, setAuditLogs] = useState<Array<Record<string, unknown>> | null>(null);
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null);
  const [permissionResult, setPermissionResult] = useState<Record<string, unknown> | null>(null);
  const [actionStatus, setActionStatus] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [stagedResult, setStagedResult] = useState<Record<string, unknown> | null>(null);
  const [lintResult, setLintResult] = useState<Record<string, unknown> | null>(null);
  const [recommendations, setRecommendations] = useState<Record<string, unknown> | null>(null);
  const [selectedPackForLint, setSelectedPackForLint] = useState("");

  // New v2.7.0 features state
  const [exportWfId, setExportWfId] = useState("");
  const [exportWfPath, setExportWfPath] = useState("");
  const [importWfPath, setImportWfPath] = useState("");
  const [importWfConfirm, setImportWfConfirm] = useState(false);
  const [validateWfPath, setValidateWfPath] = useState("");

  const [packWfIds, setPackWfIds] = useState("");
  const [packIdInput, setPackIdInput] = useState("");
  const [packPathInput, setPackPathInput] = useState("");
  const [packNameInput, setPackNameInput] = useState("");
  const [packVersionInput, setPackVersionInput] = useState("");
  const [importPackPath, setImportPackPath] = useState("");
  const [importPackConfirm, setImportPackConfirm] = useState(false);
  const [inspectPackPath, setInspectPackPath] = useState("");

  const [valBackupPath, setValBackupPath] = useState("");
  const [inspectBackupPathInput, setInspectBackupPathInput] = useState("");
  const [restoreBackupPathInput, setRestoreBackupPathInput] = useState("");
  const [restoreBackupConfirm, setRestoreBackupConfirm] = useState(false);

  const [apiResult, setApiResult] = useState<unknown | null>(null);
  const [apiResultTitle, setApiResultTitle] = useState("");

  async function handleExportWorkflow() {
    if (!exportWfId || !exportWfPath) return;
    setActionStatus("Exporting workflow...");
    try {
      const data = await apiPost<any>(`/api/skills/workflows/${encodeURIComponent(exportWfId)}/export`, { output_path: exportWfPath });
      setApiResult(data);
      setApiResultTitle("Export Workflow Result");
      setActionStatus(data.status === "error" ? "Export failed" : "Workflow exported successfully");
    } catch { setActionStatus("Export failed."); }
  }

  async function handleImportWorkflow() {
    if (!importWfPath) return;
    setActionStatus("Importing workflow...");
    try {
      const data = await apiPost<any>("/api/skills/workflows/import", { archive_path: importWfPath, confirm: importWfConfirm });
      setApiResult(data);
      setApiResultTitle("Import Workflow Result");
      setActionStatus(data.status === "imported" ? "Workflow imported successfully" : "Import failed");
    } catch { setActionStatus("Import failed."); }
  }

  async function handleValidateWorkflowFile() {
    if (!validateWfPath) return;
    setActionStatus("Validating workflow package...");
    try {
      const data = await apiPost<any>("/api/skills/workflows/validate-file", { archive_path: validateWfPath });
      setApiResult(data);
      setApiResultTitle("Validate Package Result");
      setActionStatus(data.status === "failed" ? "Validation failed" : "Validation passed");
    } catch { setActionStatus("Validation failed."); }
  }

  async function handleExportPack() {
    if (!packIdInput || !packPathInput) return;
    setActionStatus("Exporting pack...");
    const wfIds = packWfIds ? packWfIds.split(",").map(s => s.trim()).filter(Boolean) : [];
    try {
      const data = await apiPost<any>("/api/skills/workflows/packs/export", {
        workflow_ids: wfIds,
        pack_id: packIdInput,
        output_path: packPathInput,
        metadata: { name: packNameInput, version: packVersionInput }
      });
      setApiResult(data);
      setApiResultTitle("Export Pack Result");
      setActionStatus(data.status === "error" ? "Export failed" : "Pack exported successfully");
    } catch { setActionStatus("Export failed."); }
  }

  async function handleImportPack() {
    if (!importPackPath) return;
    setActionStatus("Importing pack...");
    try {
      const data = await apiPost<any>("/api/skills/workflows/packs/import", { archive_path: importPackPath, confirm: importPackConfirm });
      setApiResult(data);
      setApiResultTitle("Import Pack Result");
      setActionStatus(data.status === "imported" ? "Pack imported successfully" : "Import failed");
    } catch { setActionStatus("Import failed."); }
  }

  async function handleInspectPack() {
    if (!inspectPackPath) return;
    setActionStatus("Inspecting pack...");
    try {
      const data = await apiPost<any>("/api/skills/workflows/packs/inspect", { archive_path: inspectPackPath });
      setApiResult(data);
      setApiResultTitle("Inspect Pack Result");
      setActionStatus(data.status === "ok" ? "Pack inspected successfully" : "Inspection failed");
    } catch { setActionStatus("Inspection failed."); }
  }

  async function handleValidateBackup() {
    if (!valBackupPath) return;
    setActionStatus("Validating backup...");
    try {
      const data = await apiPost<any>("/api/backup/validate", { file_path: valBackupPath });
      setApiResult(data);
      setApiResultTitle("Validate Backup Result");
      setActionStatus(data.status === "failed" ? "Backup validation failed" : "Backup validation passed");
    } catch { setActionStatus("Validation failed."); }
  }

  async function handleInspectBackup() {
    if (!inspectBackupPathInput) return;
    setActionStatus("Inspecting backup...");
    try {
      const data = await apiPost<any>("/api/backup/inspect", { file_path: inspectBackupPathInput });
      setApiResult(data);
      setApiResultTitle("Inspect Backup Result");
      setActionStatus(data.status === "ok" ? "Backup inspected successfully" : "Inspection failed");
    } catch { setActionStatus("Inspection failed."); }
  }

  async function handleRestoreBackup() {
    if (!restoreBackupPathInput) return;
    setActionStatus("Restoring backup...");
    try {
      const data = await apiPost<any>("/api/backup/restore", { file_path: restoreBackupPathInput, confirm: restoreBackupConfirm });
      setApiResult(data);
      setApiResultTitle("Restore Backup Result");
      setActionStatus(data.status === "restored" ? "Backup restored successfully" : "Restore failed");
    } catch { setActionStatus("Restore failed."); }
  }


  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/skills/workflows").then((d) => setWorkflows((d.workflows as Array<Record<string, unknown>>) || [])).catch(() => {});
    apiGet<Record<string, unknown>>("/api/skills/workflows/audit?limit=20").then((d) => setAuditLogs((d.runs as Array<Record<string, unknown>>) || [])).catch(() => {});
    apiGet<Record<string, unknown>>("/api/skills/recommend?explain=true").then((d) => setRecommendations(d)).catch(() => {});
  }, []);

  async function handleDiscover() {
    setActionStatus("Discovering workflows...");
    try {
      const res = await fetch("/api/skills/workflows/discover", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ paths: ["examples/workflows"] }) });
      const data = await res.json();
      setActionStatus(`Discovered ${data.count} workflows`);
      apiGet<Record<string, unknown>>("/api/skills/workflows").then((d) => setWorkflows((d.workflows as Array<Record<string, unknown>>) || [])).catch(() => {});
    } catch { setActionStatus("Discovery failed."); }
  }

  async function handlePreview(wf: Record<string, unknown>) {
    setActionStatus(`Previewing ${String(wf.workflow_id)}...`);
    try {
      const res = await fetch(`/api/skills/workflows/${encodeURIComponent(String(wf.workflow_id))}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inputs: {} }) });
      const data = await res.json();
      setPreviewResult(data);
      setActionStatus("Preview complete");
    } catch { setActionStatus("Preview failed."); }
  }

  async function handlePermissions(wf: Record<string, unknown>) {
    setActionStatus(`Fetching permissions for ${String(wf.workflow_id)}...`);
    try {
      const res = await fetch(`/api/skills/workflows/${encodeURIComponent(String(wf.workflow_id))}/permissions`);
      const data = await res.json();
      setPermissionResult(data);
      setActionStatus("Permissions fetched");
    } catch { setActionStatus("Permissions fetch failed."); }
  }

  async function handleDryRun(wf: Record<string, unknown>) {
    setActionStatus(`Dry running ${String(wf.workflow_id)}...`);
    try {
      const res = await fetch(`/api/skills/workflows/${encodeURIComponent(String(wf.workflow_id))}/run-dry`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inputs: {} }) });
      const data = await res.json();
      setPreviewResult(data);
      setActionStatus(`Dry run: ${data.status}`);
    } catch { setActionStatus("Dry run failed."); }
  }

  async function handleRun(wf: Record<string, unknown>) {
    if (!confirm(`Run workflow '${wf.name}'? This will execute skills.`)) return;
    setActionStatus(`Running ${String(wf.workflow_id)}...`);
    try {
      const res = await fetch(`/api/skills/workflows/${encodeURIComponent(String(wf.workflow_id))}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ inputs: {} }) });
      const data = await res.json();
      setPreviewResult(data);
      setActionStatus(`Run: ${data.status}`);
    } catch { setActionStatus("Run failed."); }
  }

  async function handlePreviewUrl() {
    if (!urlInput) return;
    setActionStatus("Previewing URL...");
    try {
      const res = await fetch("/api/skills/url-import/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url: urlInput }) });
      const data = await res.json();
      setStagedResult(data);
      setActionStatus(data.staged_id ? `Staged: ${data.staged_id}` : "Preview failed");
    } catch { setActionStatus("URL preview failed."); }
  }

  async function handleImportStaged(stagedId: string) {
    if (!confirm(`Import staged pack '${stagedId}'? Skills will remain disabled.`)) return;
    setActionStatus(`Importing ${stagedId}...`);
    try {
      const res = await fetch("/api/skills/url-import/import-staged", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ staged_id: stagedId, confirm: true }) });
      const data = await res.json();
      setStagedResult(data);
      setActionStatus(`Imported: ${data.status}`);
    } catch { setActionStatus("Import failed."); }
  }

  async function handleInstallStaged(stagedId: string) {
    if (!confirm(`Install staged pack '${stagedId}'? Skills remain disabled by default.`)) return;
    setActionStatus(`Installing ${stagedId}...`);
    try {
      const res = await fetch("/api/skills/url-import/install-staged", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ staged_id: stagedId, confirm: true }) });
      const data = await res.json();
      setStagedResult(data);
      setActionStatus(`Installed: ${data.status}`);
    } catch { setActionStatus("Install failed."); }
  }

  async function handleLintPack() {
    if (!selectedPackForLint) return;
    setActionStatus(`Linting ${selectedPackForLint}...`);
    try {
      const res = await fetch("/api/skills/packs/lint", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: selectedPackForLint, fix_suggestions: true }) });
      const data = await res.json();
      setLintResult(data);
      setActionStatus(`Lint: ${data.grade || data.status}`);
    } catch { setActionStatus("Lint failed."); }
  }

  async function handleApplyFixes() {
    if (!lintResult || !lintResult.lint_id) return;
    if (!confirm("Apply safe lint fixes? Only templates will be modified.")) return;
    setActionStatus("Applying fixes...");
    try {
      const res = await fetch("/api/skills/packs/lint/apply-safe-fixes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lint_id: lintResult.lint_id, confirm: true }) });
      const data = await res.json();
      setLintResult(data);
      setActionStatus(`Fixes applied: ${data.status}`);
    } catch { setActionStatus("Apply fixes failed."); }
  }

  const list = workflows || [];
  const audit = auditLogs || [];
  const recs = ((recommendations?.recommendations as Array<Record<string, unknown>>) || []);

  return (
    <div className="settings-section">
      <p className="setting-note">Workflow templates combine multiple skills into step-by-step pipelines. Execution requires explicit confirmation. URL import is staged and disabled by default.</p>

      <h4>Workflow Templates</h4>
      {list.length === 0 && <p className="setting-empty">No workflows discovered. Click Discover to scan examples/workflows/.</p>}
      <div className="setting-row">
        <button className="setting-btn" onClick={handleDiscover}>Discover Workflows</button>
      </div>
      {list.map((wf) => {
        const perms = (wf.required_permissions as string[]) || [];
        const missing = (wf.missing_skills as string[]) || [];
        const status = String(wf.status || (missing.length > 0 ? "missing skills" : wf.risk_level || "ready"));
        return (
          <div key={String(wf.workflow_id)} className="workflow-card">
            <div className="workflow-header">
              <span className="workflow-name">{String(wf.name)}</span>
              <span className="workflow-id mono">{String(wf.workflow_id)}</span>
              <span className={`workflow-badge status-${status}`}>{status}</span>
              <span className={`workflow-badge risk-${String(wf.risk_level || "low")}`}>{String(wf.risk_level || "low")}</span>
            </div>
            <div className="workflow-details">
              <span className="workflow-desc">{String(wf.description)}</span>
              <span className="workflow-source mono">{String(wf.source || wf.pack_id)}</span>
              <span className="workflow-version">v{String(wf.version)}</span>
            </div>
            {perms.length > 0 && (
              <div className="workflow-permissions">
                <span className="setting-label">Permissions:</span>
                <span className="workflow-perm-list">{perms.join(", ")}</span>
              </div>
            )}
            {missing.length > 0 && (
              <div className="workflow-missing">
                <span className="setting-label">Missing Skills:</span>
                <span className="workflow-missing-list">{missing.join(", ")}</span>
              </div>
            )}
            <div className="workflow-actions">
              <button className="setting-btn" onClick={() => handlePreview(wf)}>Preview</button>
              <button className="setting-btn" onClick={() => handlePermissions(wf)}>Permissions</button>
              <button className="export-btn" onClick={() => handleDryRun(wf)}>Dry Run</button>
              <button className="setting-btn" onClick={() => handleRun(wf)}>Run</button>
            </div>
          </div>
        );
      })}

      <h4>Workflow Audit / History</h4>
      {audit.length === 0 && <p className="setting-empty">No workflow runs recorded yet.</p>}
      {audit.slice(0, 10).map((run) => (
        <div key={String(run.run_id)} className="setting-row">
          <span className="workflow-id mono">{String(run.workflow_id)}</span>
          <span className={`setting-value ${String(run.status) === "completed" ? "status-good" : "status-warn"}`}>{String(run.status)}</span>
          <span className="mono">{String(run.duration_ms)}ms</span>
          <span className="mono">{String(run.completed_steps)} steps</span>
          {run.failed_step ? <span className="status-warn">failed: {String(run.failed_step)}</span> : null}
          <span className="mono">{new Date(String(run.timestamp)).toLocaleString()}</span>
        </div>
      ))}

      <h4>Workflow Preview Panel</h4>
      {previewResult ? (
        <div className="workflow-preview-panel">
          <div className="workflow-preview-header">
            <span className={`workflow-preview-status status-${String(previewResult.status || "unknown")}`}>{String(previewResult.status || "unknown")}</span>
            <span className="workflow-preview-id mono">{String((previewResult as any).workflow_id || "")}</span>
          </div>
          <div className="workflow-preview-steps">
            {((previewResult.steps || []) as any[]).map((step, idx) => (
              <div key={idx} className="workflow-preview-step">
                <span className="workflow-step-id">{step.step_id}</span>
                <span className="workflow-step-skill">{step.skill_id}</span>
                <span className="workflow-step-command">{step.command}</span>
                <span className={`workflow-step-status ${step.installed ? "installed" : "missing"}`}>
                  {step.installed ? (step.enabled ? "enabled" : "disabled") : "missing"}
                </span>
                {step.output_key && <span className="workflow-step-output">output: {step.output_key}</span>}
                {step.warnings && (step.warnings as string[]).length > 0 ? (
                  <span className="workflow-step-warnings status-warn">{(step.warnings as string[]).join("; ")}</span>
                ) : null}
              </div>
            ))}
          </div>
          {previewResult.warnings && (previewResult.warnings as string[]).length > 0 ? (
            <div className="workflow-preview-warnings status-warn">{(previewResult.warnings as string[]).join("; ")}</div>
          ) : null}
          {previewResult.blocked_reason ? (
            <div className="workflow-preview-blocked status-warn">Blocked: {String(previewResult.blocked_reason)}</div>
          ) : null}
        </div>
      ) : (
        <p className="setting-empty">Select a workflow to preview.</p>
      )}

      <h4>Workflow Permission Review Panel</h4>
      {permissionResult ? (
        <div className="workflow-permission-panel">
          <div className="workflow-perm-header">
            <span className="workflow-perm-workflow">{String((permissionResult as any).workflow_id || "")}</span>
            <span className={`workflow-perm-status status-${String(permissionResult.status || "unknown")}`}>{String(permissionResult.status || "unknown")}</span>
          </div>
          <div className="workflow-perm-table">
            {((permissionResult.permissions || []) as any[]).map((perm, idx) => (
              <div key={idx} className="workflow-perm-row">
                <span className="workflow-perm-name">{perm.permission}</span>
                <span className="workflow-perm-skill">{perm.required_by}</span>
                <span className={`workflow-perm-risk risk-${String(perm.risk_level || "low")}`}>{String(perm.risk_level || "low")}</span>
                <span className={`workflow-perm-approved ${perm.approved ? "yes" : "no"}`}>{perm.approved ? "✓" : "✗"}</span>
              </div>
            ))}
          </div>
          {permissionResult.approval_required ? (
            <div className="workflow-perm-approval-required status-warn">Approval required for critical permissions.</div>
          ) : null}
        </div>
      ) : (
        <p className="setting-empty">Select a workflow to review permissions.</p>
      )}

      <h4>URL Staged Import Flow</h4>
      <p className="setting-note">HTTPS required. Not a marketplace. Skills remain disabled after install. Review permissions before enabling.</p>
      <div className="setting-row">
        <input className="setting-input" type="text" placeholder="https://example.com/pack.zip" value={urlInput} onChange={(e) => setUrlInput(e.target.value)} />
        <button className="setting-btn" onClick={handlePreviewUrl}>Preview URL</button>
      </div>
      {stagedResult && stagedResult.staged_id ? (
        <div className="workflow-staged-panel">
          <div className="workflow-staged-id">Staged ID: <span className="mono">{String(stagedResult.staged_id)}</span></div>
          <div className="workflow-staged-meta">
            <span className="workflow-staged-name">{String(stagedResult.name || "")}</span>
            <span className="workflow-staged-version">v{String(stagedResult.version || "")}</span>
            <span className={`workflow-staged-trust ${String(stagedResult.trust || "unknown")}`}>{String(stagedResult.trust || "unknown")}</span>
          </div>
          {stagedResult.risk_summary ? <div className="workflow-staged-risk status-warn">{String(stagedResult.risk_summary)}</div> : null}
          {stagedResult.dependencies && (stagedResult.dependencies as string[]).length > 0 ? (
            <div className="workflow-staged-deps">
              <span className="setting-label">Dependencies:</span>
              <span className="workflow-staged-deps-list">{(stagedResult.dependencies as string[]).join(", ")}</span>
            </div>
          ) : null}
          <div className="workflow-staged-actions">
            <button className="setting-btn" onClick={() => stagedResult.staged_id && handleImportStaged(String(stagedResult.staged_id))}>Import Staged</button>
            <button className="danger-btn" onClick={() => stagedResult.staged_id && handleInstallStaged(String(stagedResult.staged_id))}>Install Staged</button>
          </div>
        </div>
      ) : null}

      <h4>Lint Fix Suggestions</h4>
      <p className="setting-note">Safe fixes only. Templates modified. Code and permissions unchanged. Confirmation required.</p>
      <div className="setting-row">
        <input className="setting-input" type="text" placeholder="./examples/skill-packs/csv-analysis-pack" value={selectedPackForLint} onChange={(e) => setSelectedPackForLint(e.target.value)} />
        <button className="setting-btn" onClick={handleLintPack}>Lint Pack</button>
      </div>
      {lintResult && (
        <div className="workflow-lint-panel">
          <div className="workflow-lint-score">
            <span className="workflow-lint-grade">Grade: <span className={`workflow-grade-${lintResult.grade || "unknown"}`}>{String(lintResult.grade || "unknown")}</span></span>
            <span className="workflow-lint-score-val">Score: {String(lintResult.score || 0)}</span>
          </div>
          {lintResult.issues && (lintResult.issues as any[]).length > 0 ? (
            <div className="workflow-lint-issues">
              <span className="setting-label">Issues:</span>
              <ul>{(lintResult.issues as any[]).map((issue, idx) => (<li key={idx}><span className="status-warn">{issue.type}</span>: {issue.message}</li>))}</ul>
            </div>
          ) : null}
          {lintResult.recommendations && (lintResult.recommendations as any[]).length > 0 ? (
            <div className="workflow-lint-recommendations">
              <span className="setting-label">Recommendations:</span>
              <ul>{(lintResult.recommendations as any[]).map((rec, idx) => (<li key={idx}>{rec.message}</li>))}</ul>
            </div>
          ) : null}
          {lintResult.fix_suggestions && (lintResult.fix_suggestions as any[]).length > 0 ? (
            <div className="workflow-lint-fixes">
              <span className="setting-label">Fix Suggestions:</span>
              <ul>{(lintResult.fix_suggestions as any[]).map((fix, idx) => (<li key={idx}>{fix.description}</li>))}</ul>
            </div>
          ) : null}
          <button className="export-btn" onClick={handleApplyFixes}>Apply Safe Fixes</button>
        </div>
      )}

      <h4>Recommendation Ranking</h4>
      <p className="setting-note">Local-only. No telemetry. No external calls. No marketplace claims.</p>
      {recs.length === 0 && <p className="setting-empty">No recommendations available.</p>}
      {recs.map((rec, idx) => (
        <div key={idx} className="workflow-recommendation">
          <div className="workflow-recommend-header">
            <span className="workflow-recommend-name">{String(rec.name || rec.pack_id)}</span>
            <span className="workflow-recommend-score">Score: {String(rec.score || 0)}</span>
          </div>
          <div className="workflow-recommend-body">
            <span className="workflow-recommend-reason">{String(rec.reason || "")}</span>
            {rec.factor_breakdown && Object.entries(rec.factor_breakdown as Record<string, unknown>).length > 0 ? (
              <div className="workflow-recommend-factors">
                <span className="setting-label">Factors:</span>
                <ul>{Object.entries(rec.factor_breakdown as Record<string, unknown>).map(([key, val]) => (<li key={key}><span className="workflow-factor-name">{key}:</span> {String(val)}</li>))}</ul>
              </div>
            ) : null}
            <div className="workflow-recommend-meta">
              <span className="workflow-recommend-source">Source: {String(rec.source || "local catalog")}</span>
              <span className={`workflow-recommend-installed ${rec.installed ? "yes" : "no"}`}>{rec.installed ? "installed" : "available"}</span>
            </div>
            {rec.risk_summary ? <span className="workflow-recommend-risk status-warn">{String(rec.risk_summary)}</span> : null}
          </div>
        </div>
      ))}

      <h4>v2.7.0 Advanced Operations</h4>
      <p className="setting-note">Export, import, and validate workflows, packs, and system backups.</p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px", marginTop: "15px", marginBottom: "20px" }}>
        {/* Workflow Import/Export Panel */}
        <div style={{ background: "rgba(10, 15, 20, 0.5)", padding: "15px", borderRadius: "8px", border: "1px solid #21333a" }}>
          <h5>Workflow Import &amp; Export</h5>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "10px" }}>
            <label className="setting-label">Export Workflow</label>
            <input className="setting-input" type="text" placeholder="Workflow ID" value={exportWfId} onChange={(e) => setExportWfId(e.target.value)} />
            <input className="setting-input" type="text" placeholder="Output path (.liuantworkflow)" value={exportWfPath} onChange={(e) => setExportWfPath(e.target.value)} />
            <button className="setting-btn" onClick={handleExportWorkflow}>Export</button>

            <hr style={{ borderColor: "#21333a", margin: "10px 0" }} />

            <label className="setting-label">Import Workflow</label>
            <input className="setting-input" type="text" placeholder="Archive path (.liuantworkflow)" value={importWfPath} onChange={(e) => setImportWfPath(e.target.value)} />
            <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#9fb1ad", cursor: "pointer" }}>
              <input type="checkbox" checked={importWfConfirm} onChange={(e) => setImportWfConfirm(e.target.checked)} /> Confirm (Safe Mode)
            </label>
            <button className="setting-btn" onClick={handleImportWorkflow}>Import</button>

            <hr style={{ borderColor: "#21333a", margin: "10px 0" }} />

            <label className="setting-label">Validate Package</label>
            <input className="setting-input" type="text" placeholder="Package archive path" value={validateWfPath} onChange={(e) => setValidateWfPath(e.target.value)} />
            <button className="setting-btn" onClick={handleValidateWorkflowFile}>Validate</button>
          </div>
        </div>

        {/* Workflow Packs Panel */}
        <div style={{ background: "rgba(10, 15, 20, 0.5)", padding: "15px", borderRadius: "8px", border: "1px solid #21333a" }}>
          <h5>Workflow Packs</h5>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "10px" }}>
            <label className="setting-label">Export Pack</label>
            <input className="setting-input" type="text" placeholder="Workflow IDs (comma separated)" value={packWfIds} onChange={(e) => setPackWfIds(e.target.value)} />
            <input className="setting-input" type="text" placeholder="Pack ID" value={packIdInput} onChange={(e) => setPackIdInput(e.target.value)} />
            <input className="setting-input" type="text" placeholder="Output path (.liuantworkflowpack)" value={packPathInput} onChange={(e) => setPackPathInput(e.target.value)} />
            <input className="setting-input" type="text" placeholder="Name" value={packNameInput} onChange={(e) => setPackNameInput(e.target.value)} />
            <input className="setting-input" type="text" placeholder="Version (e.g. 1.0.0)" value={packVersionInput} onChange={(e) => setPackVersionInput(e.target.value)} />
            <button className="setting-btn" onClick={handleExportPack}>Export Pack</button>

            <hr style={{ borderColor: "#21333a", margin: "10px 0" }} />

            <label className="setting-label">Import Pack</label>
            <input className="setting-input" type="text" placeholder="Pack archive path (.liuantworkflowpack)" value={importPackPath} onChange={(e) => setImportPackPath(e.target.value)} />
            <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#9fb1ad", cursor: "pointer" }}>
              <input type="checkbox" checked={importPackConfirm} onChange={(e) => setImportPackConfirm(e.target.checked)} /> Confirm (Safe Mode)
            </label>
            <button className="setting-btn" onClick={handleImportPack}>Import Pack</button>

            <hr style={{ borderColor: "#21333a", margin: "10px 0" }} />

            <label className="setting-label">Inspect Pack</label>
            <input className="setting-input" type="text" placeholder="Pack archive path" value={inspectPackPath} onChange={(e) => setInspectPackPath(e.target.value)} />
            <button className="setting-btn" onClick={handleInspectPack}>Inspect Pack</button>
          </div>
        </div>

        {/* Backup & Restore Panel */}
        <div style={{ background: "rgba(10, 15, 20, 0.5)", padding: "15px", borderRadius: "8px", border: "1px solid #21333a" }}>
          <h5>Backup &amp; Restore</h5>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "10px" }}>
            <label className="setting-label">Validate Backup</label>
            <input className="setting-input" type="text" placeholder="Backup file path (.liuantbackup)" value={valBackupPath} onChange={(e) => setValBackupPath(e.target.value)} />
            <button className="setting-btn" onClick={handleValidateBackup}>Validate</button>

            <hr style={{ borderColor: "#21333a", margin: "10px 0" }} />

            <label className="setting-label">Inspect Backup</label>
            <input className="setting-input" type="text" placeholder="Backup file path" value={inspectBackupPathInput} onChange={(e) => setInspectBackupPathInput(e.target.value)} />
            <button className="setting-btn" onClick={handleInspectBackup}>Inspect</button>

            <hr style={{ borderColor: "#21333a", margin: "10px 0" }} />

            <label className="setting-label">Restore Backup</label>
            <input className="setting-input" type="text" placeholder="Backup file path" value={restoreBackupPathInput} onChange={(e) => setRestoreBackupPathInput(e.target.value)} />
            <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#9fb1ad", cursor: "pointer" }}>
              <input type="checkbox" checked={restoreBackupConfirm} onChange={(e) => setRestoreBackupConfirm(e.target.checked)} /> Confirm Restore (Safe Mode)
            </label>
            <button className="setting-btn" onClick={handleRestoreBackup}>Restore</button>
          </div>
        </div>
      </div>

      {!!apiResult && (
        <div style={{ marginTop: "20px", marginBottom: "20px", padding: "15px", background: "#0c1217", border: "1px solid #21333a", borderRadius: "8px" }}>
          <h5 style={{ margin: "0 0 10px 0" }}>{apiResultTitle}</h5>
          <pre style={{ overflowX: "auto", padding: "10px", background: "#05070a", borderRadius: "4px", fontSize: "12px" }}>
            {JSON.stringify(apiResult, null, 2)}
          </pre>
        </div>
      )}

      <h4>CLI Commands</h4>
      <div className="setting-commands">
        <code>./liuant skills workflow list</code>
        <code>./liuant skills workflow discover</code>
        <code>./liuant skills workflow validate csv-analysis-report</code>
        <code>./liuant skills workflow inspect csv-analysis-report</code>
        <code>./liuant skills workflow preview csv-analysis-report</code>
        <code>./liuant skills workflow permissions csv-analysis-report</code>
        <code>./liuant skills workflow run csv-analysis-report --dry-run</code>
        <code>./liuant skills workflow audit --latest</code>
        <code>./liuant skills recommend analytics --explain</code>
        <code>./liuant skills catalog</code>
      </div>
      {actionStatus && <p className="setting-note">{actionStatus}</p>}
    </div>
  );
}

function UsageSettings() {
  const [budget, setBudget] = useState<Record<string, unknown> | null>(null);
  const [alerts, setAlerts] = useState<Record<string, unknown> | null>(null);
  const [dailyLimit, setDailyLimit] = useState("");
  const [monthlyLimit, setMonthlyLimit] = useState("");
  const [actionStatus, setActionStatus] = useState("");

  const fetchBudget = () => {
    apiGet<Record<string, unknown>>("/api/usage/budget")
      .then((data) => {
        setBudget(data);
        setDailyLimit(String(data.daily_estimated_cost_limit ?? "0.0"));
        setMonthlyLimit(String(data.monthly_estimated_cost_limit ?? "0.0"));
      })
      .catch(() => {});
  };

  const fetchAlerts = () => {
    apiGet<Record<string, unknown>>("/api/usage/alerts")
      .then(setAlerts)
      .catch(() => {});
  };

  useEffect(() => {
    fetchBudget();
    fetchAlerts();
  }, []);

  async function handleSaveBudget() {
    setActionStatus("Saving budget...");
    try {
      await apiPost("/api/usage/budget", {
        daily_estimated_cost_limit: parseFloat(dailyLimit) || 0.0,
        monthly_estimated_cost_limit: parseFloat(monthlyLimit) || 0.0,
      });
      setActionStatus("Budget saved");
      fetchBudget();
      fetchAlerts();
    } catch {
      setActionStatus("Failed to save budget.");
    }
  }

  async function handleExport(format: string) {
    setActionStatus(`Exporting ${format}...`);
    try {
      const data = await apiPost<{ path: string; records: number }>("/api/usage/export", { format });
      setActionStatus(`Exported ${data.records} records to ${data.path}`);
    } catch {
      setActionStatus("Export failed.");
    }
  }

  const alertList = (alerts?.alerts as Array<Record<string, unknown>>) || [];

  return (
    <div className="settings-section">
      <h4>Budget Settings</h4>
      <p className="setting-note">Set cost limits for cloud models. Local models (Ollama, LM Studio) are always free.</p>
      
      <div className="setting-row">
        <span className="setting-label">Daily Cost Limit (USD)</span>
        <input 
          className="setting-input" 
          type="number" 
          step="0.01" 
          value={dailyLimit} 
          onChange={(e) => setDailyLimit(e.target.value)} 
          name="daily_estimated_cost_limit"
        />
      </div>

      <div className="setting-row">
        <span className="setting-label">Monthly Cost Limit (USD)</span>
        <input 
          className="setting-input" 
          type="number" 
          step="0.01" 
          value={monthlyLimit} 
          onChange={(e) => setMonthlyLimit(e.target.value)} 
          name="monthly_estimated_cost_limit"
        />
      </div>

      <div className="setting-row">
        <button className="setting-btn" onClick={handleSaveBudget}>Save Budget Settings</button>
      </div>

      <h4>Budget Alerts & Anomaly Warnings</h4>
      <div id="budget-alerts" className="budget-alerts-container">
        {alertList.length === 0 ? (
          <p className="setting-empty">No active budget alerts.</p>
        ) : (
          alertList.map((a, idx) => (
            <div key={idx} className={`alert-card status-warn`}>
              <span className="alert-message">{String(a.message || a.type)}</span>
              {a.pct ? <span className="alert-pct">{String(a.pct)}% used</span> : null}
            </div>
          ))
        )}
      </div>

      <h4>Export Usage Logs</h4>
      <p className="setting-note">Export raw local usage logs. Sensitive information (API keys, etc.) is automatically redacted.</p>
      <div id="export-buttons" className="setting-row export-buttons-container">
        <button className="setting-btn" onClick={() => handleExport("csv")}>Export CSV</button>
        <button className="setting-btn" onClick={() => handleExport("json")}>Export JSON</button>
        <button className="setting-btn" onClick={() => handleExport("markdown")}>Export Markdown</button>
      </div>

      {actionStatus && <p className="setting-note">{actionStatus}</p>}
    </div>
  );
}

function VoiceSettings() {
  const [voiceSettings, setVoiceSettings] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = () => {
    setLoading(true);
    apiGet<Record<string, any>>("/api/voice/settings")
      .then(setVoiceSettings)
      .catch((e) => setStatus(`Error loading voice settings: ${e}`))
      .finally(() => setLoading(false));
  };

  const handleToggle = (key: string) => {
    const newVal = !voiceSettings[key];
    const payload = { ...voiceSettings, [key]: newVal };
    setVoiceSettings(payload);
    apiPost("/api/voice/settings", payload)
      .then(() => setStatus("Saved."))
      .catch((e) => setStatus(`Error saving: ${e}`));
  };

  const handleChange = (key: string, value: string) => {
    setVoiceSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    setStatus("Saving...");
    apiPost("/api/voice/settings", voiceSettings)
      .then(() => setStatus("Settings saved successfully."))
      .catch((e) => setStatus(`Error saving: ${e}`));
  };

  if (loading) return <LoadingSpinner label="Loading voice settings..." />;

  return (
    <div className="settings-section">
      <div className="setting-row">
        <span className="setting-label">Enable Voice Assistant</span>
        <button className={`toggle-btn ${voiceSettings.voice_enabled ? "on" : "off"}`} onClick={() => handleToggle("voice_enabled")}>
          {voiceSettings.voice_enabled ? "Enabled" : "Disabled"}
        </button>
      </div>
      
      <div className="setting-row">
        <span className="setting-label">Enable Wake Word Listening</span>
        <button className={`toggle-btn ${voiceSettings.wake_listening_enabled ? "on" : "off"}`} onClick={() => handleToggle("wake_listening_enabled")}>
          {voiceSettings.wake_listening_enabled ? "Enabled" : "Disabled"}
        </button>
      </div>

      <div className="setting-row">
        <span className="setting-label">Assistant Name</span>
        <input 
          className="setting-input" 
          value={voiceSettings.assistant_name || "Liuant"} 
          onChange={(e) => handleChange("assistant_name", e.target.value)} 
        />
      </div>

      <div className="setting-row">
        <span className="setting-label">STT Provider</span>
        <select className="setting-select" value={voiceSettings.stt_provider || "local_mock"} onChange={(e) => handleChange("stt_provider", e.target.value)}>
          <option value="local_mock">Local Mock (Testing)</option>
          <option value="system">System Default</option>
          <option value="openai_stt">OpenAI Whisper</option>
        </select>
      </div>

      <div className="setting-row">
        <span className="setting-label">TTS Provider</span>
        <select className="setting-select" value={voiceSettings.tts_provider || "system"} onChange={(e) => handleChange("tts_provider", e.target.value)}>
          <option value="system">System Default (macOS Say)</option>
          <option value="mock">Local Mock</option>
          <option value="openai_tts">OpenAI TTS</option>
        </select>
      </div>

      <div className="setting-row">
        <span className="setting-label">Redact Transcripts (Secrets)</span>
        <button className={`toggle-btn ${voiceSettings.redact_transcripts !== false ? "on" : "off"}`} onClick={() => handleToggle("redact_transcripts")}>
          {voiceSettings.redact_transcripts !== false ? "Enabled" : "Disabled"}
        </button>
      </div>

      <div className="setting-row">
        <span className="setting-label">Store Transcripts in Audit Log</span>
        <button className={`toggle-btn ${voiceSettings.store_transcripts ? "on" : "off"}`} onClick={() => handleToggle("store_transcripts")}>
          {voiceSettings.store_transcripts ? "Enabled" : "Disabled"}
        </button>
      </div>

      <div className="setting-row">
        <button className="setting-btn" onClick={handleSave}>Save Voice Settings</button>
        {status && <span className="setting-note ml-2">{status}</span>}
      </div>
    </div>
  );
}

function BrowserAutomationSettings() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [searchStatus, setSearchStatus] = useState<Record<string, unknown> | null>(null);
  
  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/browser/status").then(setStatus).catch(() => {});
    apiGet<Record<string, unknown>>("/api/search/status").then(setSearchStatus).catch(() => {});
  }, []);

  return (
    <div className="settings-section">
      <div className="setting-row"><span className="setting-label">Browser Automation</span><span className={`setting-value ${status?.enabled ? "status-good" : "status-warn"}`}>{status?.enabled ? "Enabled" : "Disabled"}</span></div>
      <div className="setting-row"><span className="setting-label">Playwright Installed</span><span className="setting-value">{status?.playwright_installed ? "Yes" : "No"}</span></div>
      <div className="setting-row"><span className="setting-label">Search Provider</span><span className="setting-value">{String(searchStatus?.provider || "None")}</span></div>
      
      <h4>Safety Rules</h4>
      <p className="setting-note">Browser automation is strictly gated. Form filling, clicks, and downloads require confirmation.</p>
      
      <h4>Commands</h4>
      <div className="setting-commands">
        <code>./liuant browser status</code>
        <code>./liuant browser enable --confirm true</code>
        <code>./liuant browser disable</code>
        <code>./liuant search providers</code>
        <code>./liuant desktop safe-apps</code>
        <code>./liuant approvals list</code>
      </div>
    </div>
  );
}
