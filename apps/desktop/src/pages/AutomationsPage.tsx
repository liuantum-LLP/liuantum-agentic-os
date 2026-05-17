import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";

export function AutomationsPage() {
  const [automations, setAutomations] = useState<Array<Record<string, unknown>> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Array<Record<string, unknown>>>("/api/automations")
      .then(setAutomations)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner label="Loading automations..." />;
  if (!automations || automations.length === 0) {
    return <EmptyState title="No automations yet" message="Create an automation through Chat. Try: 'Every morning create a task list'" />;
  }

  return (
    <div className="page-list">
      {automations.map((a) => (
        <div key={String(a.id)} className="page-list-item">
          <div className="list-item-main">
            <strong>{String(a.name || a.id || "Unnamed")}</strong>
            <span className="list-item-slug">{String(a.schedule_text || a.schedule || "")}</span>
          </div>
          <div className="list-item-meta">
            <span className={`status-tag ${String(a.enabled) === "true" ? "good" : "warn"}`}>
              {String(a.enabled) === "true" ? "enabled" : "disabled"}
            </span>
            {a.next_run_at ? <span className="list-item-detail">Next: {String(a.next_run_at).slice(0, 16)}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
