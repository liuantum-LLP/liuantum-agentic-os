import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { StatusPill } from "../components/StatusPill";

export function DashboardPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [backend, setBackend] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendOnline, setBackendOnline] = useState(false);

  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/system/dashboard")
      .then((d) => { setData(d); setBackendOnline(true); })
      .catch(() => {})
      .finally(() => setLoading(false));
    apiGet<Record<string, unknown>>("/api/system/status")
      .then((s) => setBackend(s))
      .catch(() => {});
  }, []);

  if (loading) return <LoadingSpinner label="Loading dashboard..." />;

  const version = (backend?.app_version as string) || "";
  const mode = (backend?.desktop_backend_mode as string) || "external_backend";
  const agents = ((data?.agents as Record<string, unknown>)?.count as number) || 0;
  const approvals = ((data?.approvals as Record<string, unknown>)?.pending as number) || 0;
  const campaigns = ((data?.campaigns as Record<string, unknown>)?.count as number) || 0;
  const automations = ((data?.automations as Record<string, unknown>)?.count as number) || 0;
  const providers = ((data?.providers as Record<string, unknown>)?.configured_count as number) || 0;
  const connectors = ((data?.enabled_connector_count as number)) || 0;

  return (
    <div className="dashboard-grid">
      <div className="dashboard-header">
        <h3>System Status</h3>
        <StatusPill label={backendOnline ? "Online" : "Offline"} tone={backendOnline ? "good" : "warn"} />
      </div>

      <div className="dashboard-cards">
        <div className="dash-card">
          <span className="dash-value">{version || "—"}</span>
          <span className="dash-label">Version</span>
        </div>
        <div className="dash-card">
          <span className="dash-value">{mode}</span>
          <span className="dash-label">Backend Mode</span>
        </div>
        <div className="dash-card">
          <span className="dash-value">{agents}</span>
          <span className="dash-label">Agents</span>
        </div>
        <div className="dash-card">
          <span className="dash-value">{approvals}</span>
          <span className="dash-label">Pending Approvals</span>
        </div>
        <div className="dash-card">
          <span className="dash-value">{automations}</span>
          <span className="dash-label">Automations</span>
        </div>
        <div className="dash-card">
          <span className="dash-value">{providers}/{campaigns}</span>
          <span className="dash-label">Providers / Campaigns</span>
        </div>
        <div className="dash-card">
          <span className="dash-value">{connectors}</span>
          <span className="dash-label">Connectors</span>
        </div>
      </div>

      <div className="dashboard-info">
        <p><strong>Liuant Agentic OS</strong> — local-first AI workforce platform.</p>
        <p>Use <strong>Chat</strong> to configure providers, agents, automations, and connectors.</p>
        <p>All data stays local. No cloud dependency for core features.</p>
      </div>
    </div>
  );
}
