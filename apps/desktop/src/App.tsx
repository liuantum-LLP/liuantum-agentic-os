import { useEffect, useState, useRef } from "react";
import { apiGet, apiPost, clearAuthToken, getApiBase, getAuthToken, sanitizeError, setApiBase, setAuthToken } from "./api/client";
import { ChatPage } from "./pages/ChatPage";
import { DashboardPage } from "./pages/DashboardPage";
import { AgentsPage } from "./pages/AgentsPage";
import { AutomationsPage } from "./pages/AutomationsPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { SettingsPage } from "./pages/SettingsPage";
import { OnboardingPage } from "./pages/OnboardingPage";

type NavItem = {
  id: string;
  label: string;
};

const NAV_ITEMS: NavItem[] = [
  { id: "chat", label: "Chat" },
  { id: "dashboard", label: "Dashboard" },
  { id: "agents", label: "Agents" },
  { id: "automations", label: "Automations" },
  { id: "knowledge", label: "Knowledge" },
  { id: "settings", label: "Settings" },
];

function App() {
  const [active, setActive] = useState("chat");
  const [backendOnline, setBackendOnline] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [tokenDraft, setTokenDraft] = useState("");
  const [baseDraft, setBaseDraft] = useState(getApiBase());
  const [sessionStatus, setSessionStatus] = useState(
    localStorage.getItem("LIUANT_SESSION_TOKEN") ? "session active" : "no session"
  );
  const [backendMode, setBackendMode] = useState("external_backend");
  const [showOnboarding, setShowOnboarding] = useState(
    !localStorage.getItem("LIUANT_ONBOARDING_DONE")
  );
  const [starting, setStarting] = useState(false);
  const [startMessage, setStartMessage] = useState("");
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function checkBackend() {
    try {
      const status = await apiGet<Record<string, unknown>>("/api/system/status");
      setBackendOnline(true);
      setBackendMode(String(status.desktop_backend_mode || "external_backend"));
      setStarting(false);
      setStartMessage("");
      retryRef.current = 0;
      return true;
    } catch {
      setBackendOnline(false);
      return false;
    }
  }

  function startPolling() {
    retryRef.current = 0;
    setStarting(true);
    setStartMessage("Starting Liuant...");
    poll();
  }

  async function poll() {
    const online = await checkBackend();
    if (online) return;
    retryRef.current++;
    const attempt = retryRef.current;
    const maxAttempts = 15;
    if (attempt > maxAttempts) {
      setStarting(false);
      setStartMessage("Backend could not be started automatically.");
      return;
    }
    setStartMessage(`Starting backend (attempt ${attempt}/${maxAttempts})...`);
    const delay = Math.min(1000 * Math.pow(1.3, attempt - 1), 8000);
    timerRef.current = setTimeout(poll, delay);
  }

  function handleRetry() {
    if (timerRef.current) clearTimeout(timerRef.current);
    startPolling();
  }

  useEffect(() => {
    checkBackend().then((online) => {
      if (!online) startPolling();
    });
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  async function handleLogin() {
    if (!tokenDraft) return;
    setApiBase(baseDraft);
    setAuthToken(tokenDraft);
    try {
      const result = await apiPost<{ session_token?: string }>("/api/auth/login", { token: tokenDraft });
      if (result.session_token) {
        localStorage.setItem("LIUANT_SESSION_TOKEN", result.session_token);
        setSessionStatus("session active");
      } else {
        setSessionStatus("token saved");
      }
      setTokenDraft("");
      setShowLogin(false);
      checkBackend();
    } catch {
      setSessionStatus("login failed");
    }
  }

  function handleLogout() {
    clearAuthToken();
    setTokenDraft("");
    setSessionStatus("no session");
    setShowLogin(false);
    checkBackend();
  }

  function renderPage() {
    if (starting) {
      return (
        <div className="loading-screen">
          <div className="loading-spinner" />
          <h3>{startMessage || "Starting Liuant..."}</h3>
          <p className="loading-hint">The backend is starting. Should be ready in a moment.</p>
          <div className="offline-actions">
            <button onClick={handleRetry}>Retry Now</button>
            <button className="secondary" onClick={() => { setActive("settings"); setStarting(false); }}>Advanced Setup</button>
          </div>
        </div>
      );
    }

    if (!backendOnline && active !== "settings") {
      return (
        <div className="offline-banner">
          <div className="offline-icon">
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="18" stroke="#ef4444" strokeWidth="2" opacity="0.4"/>
              <circle cx="20" cy="14" r="4" fill="#4f8cf7" opacity="0.8"/>
              <circle cx="27" cy="25" r="4" fill="#9b6ff6" opacity="0.8"/>
              <circle cx="13" cy="25" r="4" fill="#2dd4e8" opacity="0.8"/>
              <line x1="20" y1="14" x2="27" y2="25" stroke="#4f8cf7" strokeWidth="1.5" opacity="0.4"/>
              <line x1="27" y1="25" x2="13" y2="25" stroke="#9b6ff6" strokeWidth="1.5" opacity="0.4"/>
              <line x1="13" y1="25" x2="20" y2="14" stroke="#2dd4e8" strokeWidth="1.5" opacity="0.4"/>
            </svg>
          </div>
          <h3>Backend not reachable</h3>
          <p>{startMessage || "Start the Liuant backend to use the desktop app."}</p>
          <code className="offline-cmd">./liuant start</code>
          <div className="offline-actions">
            <button onClick={handleRetry}>Retry Connection</button>
            <button className="secondary" onClick={() => setShowLogin(true)}>Login</button>
            <button className="secondary" onClick={() => setActive("settings")}>Advanced Setup</button>
          </div>
          <p className="offline-hint">Run from the project root directory. The backend binds to <code>127.0.0.1:8765</code>.</p>
        </div>
      );
    }
    switch (active) {
      case "chat": return <ChatPage />;
      case "dashboard": return <DashboardPage />;
      case "agents": return <AgentsPage />;
      case "automations": return <AutomationsPage />;
      case "knowledge": return <KnowledgePage />;
      case "settings": return <SettingsPage />;
      default: return <ChatPage />;
    }
  }

  if (showOnboarding) {
    return <OnboardingPage onFinish={() => setShowOnboarding(false)} />;
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">LA</div>
          <h1>Liuant Agentic OS</h1>
          <span className="sidebar-version">v1.3.0</span>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-btn ${item.id === active ? "active" : ""}`}
              onClick={() => setActive(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className={`sidebar-status ${backendOnline ? "online" : "offline"}`}>
            <span className="status-dot" />
            <span>{backendOnline ? "Backend online" : "Backend offline"}</span>
          </div>
          <span className="sidebar-mode">{backendMode}</span>
          <button className="sidebar-login-btn" onClick={() => setShowLogin(!showLogin)}>
            {sessionStatus.includes("active") ? "Logged in" : "Login"}
          </button>
        </div>
      </aside>

      <main className="app-main">
        {showLogin && (
          <div className="login-modal">
            <div className="login-card">
              <h3>Backend Login</h3>
              <p>Enter your local API token to connect.</p>
              <label>
                Backend URL
                <input value={baseDraft} onChange={(e) => setBaseDraft(e.target.value)} />
              </label>
              <label>
                API Token
                <input value={tokenDraft} onChange={(e) => setTokenDraft(e.target.value)} type="password" />
              </label>
              <div className="login-actions">
                <button onClick={handleLogin}>Login</button>
                <button className="secondary" onClick={() => setShowLogin(false)}>Cancel</button>
                {sessionStatus.includes("active") && (
                  <button className="secondary" onClick={handleLogout}>Logout</button>
                )}
              </div>
              <p className="session-line">Session: {sessionStatus}</p>
              <p className="login-hint">Run <code>./liuant auth token</code> in terminal to get your token.</p>
            </div>
          </div>
        )}
        <div className="app-content">
          {renderPage()}
        </div>
      </main>
    </div>
  );
}

export default App;
