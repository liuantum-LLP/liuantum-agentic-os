import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";

type SettingsSection = {
  id: string;
  label: string;
};

const SECTIONS: SettingsSection[] = [
  { id: "general", label: "General" },
  { id: "providers", label: "Models & Providers" },
  { id: "connectors", label: "Connectors" },
  { id: "agents", label: "Agents" },
  { id: "automations", label: "Automations" },
  { id: "skills", label: "Skills" },
  { id: "memory", label: "Memory & Knowledge" },
  { id: "security", label: "Security" },
  { id: "backend", label: "Desktop & Backend" },
  { id: "release", label: "Release & Updates" },
];

const SECTION_HELP: Record<string, string> = {
  general: "App version, workspace path, permission mode, and local auth settings.",
  providers: "Configure AI providers and set default models for text, image, video, and embeddings.",
  connectors: "Connected external services. Use Chat to add Gmail, Telegram, LinkedIn, or X.",
  agents: "AI agents that perform tasks. Create and manage agents from here or through Chat.",
  automations: "Scheduled tasks that run agents on a recurring basis. Create and manage from Chat.",
  skills: "Installed skills extend Liuant's capabilities. Browse and install from Chat.",
  memory: "Saved facts and preferences that Liuant remembers. Say 'remember...' in Chat to add.",
  security: "API tokens, secret store status, and audit commands. Handle with care.",
  backend: "Backend connection mode, URL, and managed process controls.",
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
          {activeSection === "connectors" && <ConnectorsSettings />}
          {activeSection === "agents" && <AgentsSettings />}
          {activeSection === "automations" && <AutomationsSettings />}
          {activeSection === "skills" && <SkillsSettings />}
          {activeSection === "memory" && <MemorySettings />}
          {activeSection === "security" && <SecuritySettings />}
          {activeSection === "backend" && <BackendSettings settings={settings} />}
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
  useEffect(() => {
    apiGet<Array<Record<string, unknown>>>("/api/skills/installed").then(setInstalled).catch(() => {});
  }, []);
  const list = installed || [];
  return (
    <div className="settings-section">
      {list.length === 0 && <p className="setting-empty">No skills installed. Use Chat to browse and install skills.</p>}
      {list.map((s) => (
        <div key={String(s.skill_name || s.id)} className="setting-row">
          <span className="setting-label">{String(s.title || s.skill_name)}</span>
          <span className={`setting-value ${s.enabled ? "status-good" : "status-warn"}`}>{s.enabled ? "enabled" : "disabled"}</span>
        </div>
      ))}
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
