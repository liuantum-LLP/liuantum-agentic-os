import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { EmptyState } from "../components/EmptyState";

export function AgentsPage() {
  const [agents, setAgents] = useState<Array<Record<string, unknown>> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Array<Record<string, unknown>>>("/api/agents")
      .then(setAgents)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner label="Loading agents..." />;
  if (!agents || agents.length === 0) {
    return <EmptyState title="No agents yet" message="Create an agent through Chat. Try: 'Create a marketing agent'" />;
  }

  return (
    <div className="page-list">
      {agents.map((agent) => (
        <div key={String(agent.slug || agent.id)} className="page-list-item">
          <div className="list-item-main">
            <strong>{String(agent.name || agent.slug || "Unnamed Agent")}</strong>
            <span className="list-item-slug">{String(agent.slug || "")}</span>
          </div>
          <div className="list-item-meta">
            <span className={`status-tag ${String(agent.enabled) === "true" ? "good" : "warn"}`}>
              {String(agent.enabled) === "true" ? "enabled" : "disabled"}
            </span>
            {agent.tools ? <span className="list-item-detail">{String(agent.tools).slice(0, 60)}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}
