import { useState, useRef, useEffect } from "react";
import { apiPost } from "../api/client";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  intent?: string;
  data?: Record<string, unknown>;
  preview?: Record<string, unknown>;
  actions?: string[];
  nextQuestions?: string[];
  requiredFields?: { field: string; question: string; secret?: boolean; options?: string[] }[];
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.messages]);

  function addMessage(msg: ChatMessage) {
    setState((prev) => ({ ...prev, messages: [...prev.messages, msg] }));
  }

  async function sendMessage(message: string) {
    if (!message.trim()) return;
    addMessage({ role: "user", content: message });
    setState((prev) => ({ ...prev, loading: true }));
    try {
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
    } catch {
      addMessage({ role: "assistant", content: "Sorry, I couldn't reach the backend. Make sure the server is running.", intent: "error" });
    }
    setState((prev) => ({ ...prev, loading: false }));
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
              {msg.requiredFields && msg.requiredFields.length > 0 && msg.requiredFields[0].options && (
                <div className="chat-actions">
                  {msg.requiredFields[0].options.map((opt) => (
                    <button key={opt} className="chat-action-btn" onClick={() => handleFieldSubmit(opt)}>
                      {opt}
                    </button>
                  ))}
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
              <span className="chat-typing">thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
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
              placeholder="Ask me anything..."
              autoFocus
            />
            <button className="chat-send-btn" type="submit">Send</button>
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
