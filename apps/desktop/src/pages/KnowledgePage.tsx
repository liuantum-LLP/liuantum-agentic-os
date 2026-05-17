import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";

export function KnowledgePage() {
  const [sources, setSources] = useState<Array<Record<string, unknown>> | null>(null);
  const [memory, setMemory] = useState<Array<Record<string, unknown>> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<Array<Record<string, unknown>>>("/api/knowledge/sources").then(setSources).catch(() => setSources([])),
      apiGet<Array<Record<string, unknown>>>("/api/memory").then(setMemory).catch(() => setMemory([])),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner label="Loading knowledge..." />;

  return (
    <div className="knowledge-layout">
      <div className="knowledge-section">
        <h3>Knowledge Sources</h3>
        {(!sources || sources.length === 0) ? (
          <p className="setting-empty">No knowledge sources yet. Use Chat to add documents or type 'remember...' for quick notes.</p>
        ) : (
          <div className="page-list">
            {sources.map((s, i) => (
              <div key={String(s.id || i)} className="page-list-item">
                <div className="list-item-main">
                  <strong>{String(s.title || s.source || "Untitled")}</strong>
                  <span className="list-item-slug">{String(s.type || s.kind || "document")}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="knowledge-section">
        <h3>Memory</h3>
        {(!memory || memory.length === 0) ? (
          <p className="setting-empty">No memories saved. Say 'remember my company name is Liuant' in Chat.</p>
        ) : (
          <div className="page-list">
            {memory.slice(0, 10).map((m) => (
              <div key={String(m.id)} className="page-list-item">
                <div className="list-item-main">
                  <span className="list-item-slug">{String(m.type || "note")}</span>
                  <span className="list-item-detail">{String(m.content || "").slice(0, 100)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
