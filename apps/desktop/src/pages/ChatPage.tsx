import { useState, useRef, useEffect } from "react";
import { apiPost, apiGet } from "../api/client";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  data?: Record<string, unknown>;
  preview?: Record<string, unknown>;
  actions?: string[];
  nextQuestions?: string[];
  requiredFields?: { field: string; question: string; secret?: boolean; options?: string[] }[];
  discussionTranscript?: { role: string; round: number; content: string; status: string }[];
  discussionRoles?: string[];
  discussionWarnings?: string[];
  discussionCostNote?: string;
  providerUsed?: string;
  modelUsed?: string;
  roleUsed?: string;
  fallbackWarning?: string;
  costWarning?: string;
  discussionStreaming?: boolean;
  roleCards?: { role: string; provider: string; model: string; content: string; status: string; round: number }[];
  usageInfo?: { estimated_tokens: number; estimated_cost: number; estimated: boolean };
};

type ChatState = {
  messages: ChatMessage[];
  loading: boolean;
  waitingForField: { field: string; question: string; originalIntent: string; collected: Record<string, string> } | null;
};

const WELCOME_MESSAGE: ChatMessage = {
  role: "assistant",
  content: "Welcome to **Liuant Agentic OS**. I can help you configure and control your local AI workforce.\n\nTry asking:\n- *Show system status*\n- *Create a marketing agent*\n- *Connect Gmail*\n- *Every morning create a task list*",
  nextQuestions: ["Show system status", "Create a marketing agent", "Connect Gmail", "Every morning create a task list"],
};

export function ChatPage() {
  const [state, setState] = useState<ChatState>({
    messages: [WELCOME_MESSAGE],
    loading: false,
    waitingForField: null,
  });
  const [input, setInput] = useState("");
  const [fieldInput, setFieldInput] = useState("");
  const [discussionMode, setDiscussionMode] = useState(false);
  const [discussionRounds, setDiscussionRounds] = useState(2);
  const [discussionRoles, setDiscussionRoles] = useState<string[]>(["auto"]);
  const [discussionSettings, setDiscussionSettings] = useState<Record<string, unknown> | null>(null);
  const [streamingMode, setStreamingMode] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [streamingAbort, setStreamingAbort] = useState<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages]);

  useEffect(() => {
    apiGet<Record<string, unknown>>("/api/models/discussion")
      .then((d) => {
        setDiscussionSettings(d);
        if (d.discussion_mode_enabled === true) {
          setDiscussionMode(true);
        }
      })
      .catch(() => {});
  }, []);

  function addMessage(msg: ChatMessage) {
    setState((prev) => ({ ...prev, messages: [...prev.messages, msg] }));
  }

  const handleMicClick = () => {
    if (isListening) return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in your browser. Using simulated voice payload.");
      sendMessage("Hey Liuant, show system status");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setIsListening(true);
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      sendMessage(transcript);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognition.start();
  };

  async function sendMessage(message: string) {
    if (!message.trim()) return;
    addMessage({ role: "user", content: message });
    setState((prev) => ({ ...prev, loading: true }));
    try {
      if (discussionMode && streamingMode) {
        const abortController = new AbortController();
        setStreamingAbort(abortController);
        const msgIndex = state.messages.length;
        addMessage({ role: "assistant", content: "", intent: "discussion-streaming", discussionStreaming: true, roleCards: [] });
        let finalText = "";
        const roleCards: ChatMessage["roleCards"] = [];
        let usageInfo: ChatMessage["usageInfo"] = undefined;
        try {
          const response = await fetch("/api/chat/discussion-stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: message.trim(), roles: discussionRoles, rounds: discussionRounds }),
            signal: abortController.signal,
          });
          const reader = response.body?.getReader();
          if (!reader) throw new Error("No reader");
          const decoder = new TextDecoder();
          let buffer = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";
            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const chunk = JSON.parse(line.slice(6));
                  if (chunk.type === "role_start") {
                    roleCards.push({ role: chunk.role, provider: chunk.provider, model: chunk.model, content: "", status: "running", round: chunk.round || 1 });
                    setState((prev) => ({
                      ...prev,
                      messages: prev.messages.map((m, i) => i === msgIndex ? { ...m, roleCards: [...roleCards] } : m),
                    }));
                  } else if (chunk.type === "role_token") {
                    const lastCard = roleCards[roleCards.length - 1];
                    if (lastCard) {
                      lastCard.content += chunk.content;
                      setState((prev) => ({
                        ...prev,
                        messages: prev.messages.map((m, i) => i === msgIndex ? { ...m, roleCards: [...roleCards] } : m),
                      }));
                    }
                  } else if (chunk.type === "role_done") {
                    const lastCard = roleCards[roleCards.length - 1];
                    if (lastCard) {
                      lastCard.status = chunk.status || "completed";
                    }
                  } else if (chunk.type === "final_token") {
                    finalText += chunk.content;
                    setState((prev) => ({
                      ...prev,
                      messages: prev.messages.map((m, i) => i === msgIndex ? { ...m, content: finalText } : m),
                    }));
                  } else if (chunk.type === "usage_update") {
                    usageInfo = { estimated_tokens: chunk.estimated_tokens || 0, estimated_cost: chunk.estimated_cost || 0, estimated: chunk.estimated || true };
                  } else if (chunk.type === "error") {
                    setState((prev) => ({
                      ...prev,
                      messages: prev.messages.map((m, i) => i === msgIndex ? { ...m, content: finalText + "\n\nError: " + chunk.content } : m),
                    }));
                  } else if (chunk.type === "discussion_done") {
                    break;
                  }
                } catch {
                  // Ignore malformed SSE lines
                }
              }
            }
          }
          setState((prev) => ({
            ...prev,
            messages: prev.messages.map((m, i) => i === msgIndex ? { ...m, roleCards: [...roleCards], content: finalText || "Discussion completed.", usageInfo, discussionStreaming: false } : m),
            loading: false,
          }));
        } catch (err: unknown) {
          const errorMsg = err instanceof Error && err.name === "AbortError" ? "Streaming stopped." : `Error: ${err instanceof Error ? err.message : "Unknown"}`;
          setState((prev) => ({
            ...prev,
            messages: prev.messages.map((m, i) => i === msgIndex ? { ...m, content: finalText + "\n\n" + errorMsg, discussionStreaming: false } : m),
            loading: false,
          }));
        } finally {
          setStreamingAbort(null);
        }
      } else if (discussionMode) {
        const result = await apiPost<{
          status: string;
          final_answer: string;
          transcript?: { role: string; round: number; content: string; status: string }[];
          roles_used?: string[];
          warnings?: string[];
          cost_note?: string;
          fallback_used?: boolean;
        }>("/api/chat/discussion", { message: message.trim(), roles: discussionRoles, rounds: discussionRounds });
        const msg: ChatMessage = {
          role: "assistant",
          content: result.final_answer || "Discussion completed.",
          intent: "discussion",
          discussionTranscript: result.transcript,
          discussionRoles: result.roles_used,
          discussionWarnings: result.warnings,
          discussionCostNote: result.cost_note,
        };
        addMessage(msg);
      } else if (streamingMode) {
        const abortController = new AbortController();
        setStreamingAbort(abortController);
        const msgIndex = state.messages.length;
        addMessage({ role: "assistant", content: "", intent: "streaming" });
        let fullText = "";
        let provider = "";
        let model = "";
        try {
          const response = await fetch("/api/chat/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: message.trim() }),
            signal: abortController.signal,
          });
          const reader = response.body?.getReader();
          if (!reader) throw new Error("No reader");
          const decoder = new TextDecoder();
          let buffer = "";
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";
            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try {
                  const chunk = JSON.parse(line.slice(6));
                  if (chunk.type === "token") {
                    fullText += chunk.content;
                    provider = chunk.provider || provider;
                    model = chunk.model || model;
                    setState((prev) => ({
                      ...prev,
                      messages: prev.messages.map((m, i) =>
                        i === msgIndex ? { ...m, content: fullText, providerUsed: provider, modelUsed: model } : m
                      ),
                    }));
                  } else if (chunk.type === "error") {
                    setState((prev) => ({
                      ...prev,
                      messages: prev.messages.map((m, i) =>
                        i === msgIndex ? { ...m, content: fullText + "\n\nError: " + chunk.content } : m
                      ),
                    }));
                  } else if (chunk.type === "done") {
                    break;
                  }
                } catch {}
              }
            }
          }
        } catch (err: any) {
          if (err.name !== "AbortError") {
            setState((prev) => ({
              ...prev,
              messages: prev.messages.map((m, i) =>
                i === msgIndex ? { ...m, content: fullText || "Streaming failed. Make sure the server is running." } : m
              ),
            }));
          }
        }
        setStreamingAbort(null);
      } else {
        const result = await apiPost<{
          intent: string;
          status: string;
          message: string;
          data?: Record<string, unknown>;
          required_fields?: { field: string; question: string; secret?: boolean; options?: string[] }[];
          preview?: Record<string, unknown>;
          actions?: string[];
          next_questions?: string[];
        }>("/api/chat/message", { message: message.trim() });
        const msg: ChatMessage = {
          role: "assistant",
          content: result.message || "I processed your request.",
          intent: result.intent,
          data: result.data,
          preview: result.preview,
          actions: result.actions,
          nextQuestions: result.next_questions,
          requiredFields: result.required_fields,
          providerUsed: (result.data as any)?.provider,
          modelUsed: (result.data as any)?.model,
          roleUsed: (result.data as any)?.role_used,
          fallbackWarning: (result.data as any)?.fallback_used ? "Fallback model was used" : undefined,
        };
        addMessage(msg);
        const fields = result.required_fields;
        if (fields && fields.length > 0) {
          setState((prev) => ({
            ...prev,
            waitingForField: {
              field: fields[0].field,
              question: fields[0].question,
              originalIntent: result.intent,
              collected: {},
            },
          }));
        }
      }
    } catch {
      addMessage({ role: "assistant", content: "Sorry, I couldn't reach the backend. Make sure the server is running.", intent: "error" });
    }
    setState((prev) => ({ ...prev, loading: false }));
  }

  function stopStreaming() {
    if (streamingAbort) {
      streamingAbort.abort();
      setStreamingAbort(null);
    }
  }

  async function handleFieldSubmit(value: string) {
    if (!state.waitingForField) return;
    const wf = state.waitingForField;
    const collected = { ...wf.collected, [wf.field]: value };
    const remaining = state.messages[state.messages.length - 1]?.requiredFields?.filter(
      (f) => f.field !== wf.field
    ) || [];
    if (remaining.length > 0) {
      const next = remaining[0];
      setState((prev) => ({
        ...prev,
        waitingForField: { ...wf, field: next.field, question: next.question, collected },
      }));
      addMessage({ role: "assistant", content: next.question, requiredFields: remaining });
    } else {
      setState((prev) => ({ ...prev, waitingForField: null }));
      addMessage({ role: "user", content: `[Provided: ${wf.field}]` });
      setState((prev) => ({ ...prev, loading: true }));
      try {
        const result = await apiPost<{ status: string; message: string }>("/api/chat/action", {
          intent: wf.originalIntent,
          action: "configure",
          data: collected,
        });
        addMessage({
          role: "assistant",
          content: result.message || `Configuration saved securely.`,
          intent: wf.originalIntent,
        });
      } catch {
        addMessage({ role: "assistant", content: "Could not process configuration. Try again.", intent: "error" });
      }
      setState((prev) => ({ ...prev, loading: false }));
    }
    setFieldInput("");
  }

  function handleActionClick(action: string) {
    if (state.waitingForField) {
      handleFieldSubmit(action);
      return;
    }
    sendMessage(action);
  }

  function handleQuestionClick(q: string) {
    sendMessage(q);
  }

  function handleFormSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (state.waitingForField) {
      handleFieldSubmit(fieldInput);
    } else {
      sendMessage(input);
      setInput("");
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {state.messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-bubble">
              <div className="chat-content">{renderContent(msg.content)}</div>
              {(msg.providerUsed || msg.modelUsed || msg.roleUsed) && (
                <div className="chat-model-meta">
                  {msg.roleUsed && <span className="chat-role-badge">{msg.roleUsed}</span>}
                  {msg.providerUsed && msg.modelUsed && (
                    <span className="chat-provider-badge">{msg.providerUsed}/{msg.modelUsed}</span>
                  )}
                  {msg.fallbackWarning && <span className="chat-fallback-warning">⚠️ {msg.fallbackWarning}</span>}
                </div>
              )}
              {msg.discussionTranscript && msg.discussionTranscript.length > 0 && (
                <details className="discussion-summary">
                  <summary>Model discussion summary ({msg.discussionTranscript.length} contributions)</summary>
                  {msg.discussionRoles && (
                    <div className="discussion-roles">
                      {msg.discussionRoles.map((r, j) => (
                        <span key={j} className="discussion-role-chip">{r}</span>
                      ))}
                    </div>
                  )}
                  {msg.discussionTranscript.map((t, j) => (
                    <div key={j} className="discussion-entry">
                      <span className={`discussion-role ${t.status === "completed" ? "status-good" : "status-warn"}`}>
                        {t.role} (round {t.round})
                      </span>
                      <span className="discussion-content">{t.content.slice(0, 200)}...</span>
                    </div>
                  ))}
                  {msg.discussionWarnings && msg.discussionWarnings.length > 0 && (
                    <div className="discussion-warnings">
                      {msg.discussionWarnings.map((w, j) => (
                        <p key={j} className="discussion-warning">⚠️ {w}</p>
                      ))}
                    </div>
                  )}
                  {msg.discussionCostNote && <p className="discussion-cost-note">{msg.discussionCostNote}</p>}
                </details>
              )}
              {msg.roleCards && msg.roleCards.length > 0 && (
                <div className="discussion-role-cards">
                  <h4>Discussion Roles</h4>
                  {msg.roleCards.map((card, j) => (
                    <div key={j} className={`role-card ${card.status}`}>
                      <div className="role-card-header">
                        <span className="role-card-name">{card.role}</span>
                        <span className="role-card-round">Round {card.round}</span>
                        <span className="role-card-model">{card.provider}/{card.model}</span>
                        <span className={`role-card-status ${card.status === "completed" ? "status-good" : "status-warn"}`}>{card.status}</span>
                      </div>
                      <div className="role-card-content">{card.content.slice(0, 300)}{card.content.length > 300 ? "..." : ""}</div>
                    </div>
                  ))}
                  {msg.usageInfo && (
                    <div className="role-card-usage">
                      <span>{msg.usageInfo.estimated_tokens} tokens</span>
                      <span>~${msg.usageInfo.estimated_cost.toFixed(6)}</span>
                      <span className={msg.usageInfo.estimated ? "estimated" : "exact"}>{msg.usageInfo.estimated ? "estimated" : "exact"}</span>
                    </div>
                  )}
                </div>
              )}
              {msg.requiredFields && msg.requiredFields.length > 0 && msg.requiredFields[0].options && (
                <div className="chat-actions">
                  {msg.requiredFields[0].options.map((opt) => (
                    <button key={opt} className="chat-action-btn" onClick={() => handleFieldSubmit(opt)}>
                      {opt}
                    </button>
                  ))}
                </div>
              )}
              {msg.preview && (
                <div className="action-preview-card">
                  <div className={`action-risk risk-${String(msg.preview.risk_level || "unknown").toLowerCase()}`}>
                    {String(msg.preview.risk_level || "Unknown").toUpperCase()} RISK
                  </div>
                  <h4 className="action-title">{String(msg.preview.title || "Pending Action")}</h4>
                  <p className="action-desc">{String(msg.preview.description || "")}</p>
                  <div className="action-buttons">
                    <button className="chat-action-btn action-approve" onClick={() => handleActionClick(`Approve action ${msg.preview?.id}`)}>Approve</button>
                    <button className="chat-action-btn action-reject" onClick={() => handleActionClick(`Reject action ${msg.preview?.id}`)}>Reject</button>
                  </div>
                </div>
              )}
              {msg.nextQuestions && msg.nextQuestions.length > 0 && (
                <div className="chat-next-questions">
                  {msg.nextQuestions.map((q, j) => (
                    <button key={j} className="chat-question-btn" onClick={() => handleQuestionClick(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {state.loading && (
          <div className="chat-message assistant">
            <div className="chat-bubble">
              <span className="chat-typing">
                {state.messages[state.messages.length - 1]?.intent === "discussion-streaming"
                  ? "Models discussing (streaming)..."
                  : discussionMode
                  ? "Models discussing..."
                  : streamingMode
                  ? "Generating..."
                  : "thinking..."}
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-controls">
        <label className="chat-toggle">
          <input
            type="checkbox"
            checked={streamingMode}
            onChange={(e) => setStreamingMode(e.target.checked)}
          />
          Streaming
        </label>
        <label className="chat-toggle">
          <input
            type="checkbox"
            checked={discussionMode}
            onChange={(e) => setDiscussionMode(e.target.checked)}
          />
          Discussion Mode
        </label>
        {discussionMode && (
          <div className="chat-discussion-controls">
            <select
              className="chat-discussion-rounds"
              value={discussionRounds}
              onChange={(e) => setDiscussionRounds(parseInt(e.target.value))}
            >
              <option value={1}>1 round</option>
              <option value={2}>2 rounds</option>
              <option value={3}>3 rounds</option>
              <option value={4}>4 rounds</option>
            </select>
            <span className="chat-discussion-note">
              Uses multiple model calls per round. Cloud models incur costs.
            </span>
            {streamingMode && (
              <button
                type="button"
                className="chat-stop-btn"
                onClick={stopStreaming}
                disabled={!streamingAbort}
              >
                Stop
              </button>
            )}
          </div>
        )}
      </div>

      <form className="chat-input-area" onSubmit={handleFormSubmit}>
        {state.waitingForField ? (
          <>
            <span className="chat-field-label">{state.waitingForField.question}</span>
            <input
              ref={inputRef}
              className="chat-input"
              value={fieldInput}
              onChange={(e) => setFieldInput(e.target.value)}
              placeholder="Type your answer..."
              autoFocus
            />
            <button className="chat-send-btn" type="submit">Send</button>
          </>
        ) : (
          <>
            <input
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                discussionMode
                  ? "Ask anything — multiple models will collaborate..."
                  : streamingMode
                  ? "Ask anything — streaming response..."
                  : "Ask me anything..."
              }
              autoFocus
            />
            {streamingMode && streamingAbort ? (
              <button className="chat-stop-btn" type="button" onClick={stopStreaming}>Stop</button>
            ) : (
              <div className="chat-actions-container" style={{ display: 'flex', gap: '8px' }}>
                <button className={`chat-mic-btn ${isListening ? "listening" : ""}`} type="button" onClick={handleMicClick} title="Voice Input">
                  {isListening ? "Listening..." : "🎤"}
                </button>
                <button className="chat-send-btn" type="submit">Send</button>
              </div>
            )}
          </>
        )}
      </form>
    </div>
  );
}

function renderContent(content: string): React.ReactNode {
  const lines = content.split("\n");
  return lines.map((line, i) => {
    if (line.startsWith("## ")) return <h3 key={i} className="chat-heading">{line.slice(3)}</h3>;
    if (line.startsWith("**") && line.endsWith("**")) return <p key={i} className="chat-line chat-bold">{line.slice(2, -2)}</p>;
    if (line.startsWith("- ")) return <li key={i} className="chat-line chat-item">{line.slice(2)}</li>;
    if (line.trim() === "") return <br key={i} />;
    const rendered = line.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/_(.*?)_/g, "<em>$1</em>");
    return <p key={i} className="chat-line" dangerouslySetInnerHTML={{ __html: rendered }} />;
  });
}
