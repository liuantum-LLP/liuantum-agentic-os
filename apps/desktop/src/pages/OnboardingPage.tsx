import { useState } from "react";

type OnboardingStep = {
  id: string;
  title: string;
  description: string;
  action: string;
};

const STEPS: OnboardingStep[] = [
  {
    id: "welcome",
    title: "Welcome to Liuant Agentic OS",
    description: "Your local-first AI workforce platform. Configure everything through Chat, or dive straight into Settings. Let's get you set up in a few steps — or skip and explore on your own.",
    action: "Get Started",
  },
  {
    id: "backend",
    title: "Choose Backend Mode",
    description:
      "Liuant runs as a local backend process. Two modes are available:\n\n" +
      "• **external_backend** (recommended): Start the backend manually with `./liuant start` in your terminal. Simple and reliable.\n\n" +
      "• **managed_backend**: Liuant manages the backend process for you. Start/stop/restart from the desktop.\n\n" +
      "You can change this later in Settings > Desktop & Backend.",
    action: "Next: Connect a Provider",
  },
  {
    id: "provider",
    title: "Connect a Model Provider",
    description:
      "Liuant needs at least one AI provider to generate text, images, and more.\n\n" +
      "Supported providers: OpenAI, OpenRouter, Ollama, Kimi, Anthropic, Groq, Replicate, and more.\n\n" +
      "Go to **Chat** and say *'set openai as default'* or *'configure kimi'* to get started. Your API key will be stored securely.\n\n" +
      "Or skip this and use local-only features (agents, automations, knowledge).",
    action: "Next: Create an Agent",
  },
  {
    id: "agent",
    title: "Create Your First Agent",
    description:
      "Agents are AI workers that handle tasks for you.\n\n" +
      "Built-in agents: Content Creator, Marketing, Front Desk, Coding, Tutor, Personal Assistant.\n\n" +
      "Go to **Chat** and say *'create a marketing agent'* or *'make a personal assistant'* to create one.\n\n" +
      "Or configure agents later in Settings > Agents.",
    action: "Next: Create an Automation",
  },
  {
    id: "automation",
    title: "Create Your First Automation",
    description:
      "Automations run agents on a schedule. Examples:\n\n" +
      "• *'Every morning create a task list'*\n" +
      "• *'Every Monday summarize my emails'*\n" +
      "• *'Daily at 5pm check pending approvals'*\n\n" +
      "Go to **Chat** and describe what you want automated. Or configure in Settings > Automations.",
    action: "Next: Connect Services",
  },
  {
    id: "connectors",
    title: "Connect External Services (Optional)",
    description:
      "Liuant can connect to Gmail, Telegram, LinkedIn, and X/Twitter.\n\n" +
      "• **Gmail**: Read and draft emails (sending disabled by default)\n" +
      "• **Telegram**: Monitor a bot and create reply drafts\n" +
      "• **LinkedIn / X**: OAuth-based draft and approval-gated publishing\n\n" +
      "Go to **Chat** and say *'connect Gmail'* or *'set up Telegram'* to configure.\n\n" +
      "This step is optional. You can always add connectors later.",
    action: "Done — Show Dashboard",
  },
];

export function OnboardingPage({ onFinish }: { onFinish: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);
  const step = STEPS[stepIndex];
  const isLast = stepIndex === STEPS.length - 1;
  const isFirst = stepIndex === 0;

  function handleNext() {
    if (isLast) {
      localStorage.setItem("LIUANT_ONBOARDING_DONE", "true");
      onFinish();
    } else {
      setStepIndex((i) => i + 1);
    }
  }

  function handleSkip() {
    localStorage.setItem("LIUANT_ONBOARDING_DONE", "true");
    onFinish();
  }

  function renderDescription(text: string) {
    return text.split("\n").map((line, i) => {
      if (line.trim() === "") return <br key={i} />;
      const rendered = line
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`(.*?)`/g, "<code>$1</code>");
      return <p key={i} className="onboarding-text" dangerouslySetInnerHTML={{ __html: rendered }} />;
    });
  }

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-card">
        <div className="onboarding-steps">
          {STEPS.map((s, i) => (
            <span
              key={s.id}
              className={`onboarding-dot ${i === stepIndex ? "active" : i < stepIndex ? "done" : ""}`}
            />
          ))}
        </div>
        <h2 className="onboarding-title">{step.title}</h2>
        <div className="onboarding-description">{renderDescription(step.description)}</div>
        <div className="onboarding-actions">
          <button className="onboarding-primary" onClick={handleNext}>
            {step.action}
          </button>
          <button className="onboarding-secondary" onClick={handleSkip}>
            {isFirst ? "Skip — I know what I'm doing" : "Skip all — take me in"}
          </button>
        </div>
      </div>
    </div>
  );
}
