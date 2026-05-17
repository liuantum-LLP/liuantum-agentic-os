export type DesktopPage = {
  id: string;
  label: string;
  endpoint: string;
  description: string;
};

export const pages: DesktopPage[] = [
  { id: "chat", label: "Chat", endpoint: "/api/chat/message", description: "Control Liuant through natural language." },
  { id: "dashboard", label: "Dashboard", endpoint: "/api/system/dashboard", description: "System overview and status." },
  { id: "agents", label: "Agents", endpoint: "/api/agents", description: "Your AI agents." },
  { id: "automations", label: "Automations", endpoint: "/api/automations", description: "Recurring automated tasks." },
  { id: "knowledge", label: "Knowledge", endpoint: "/api/knowledge/sources", description: "Knowledge base and memory." },
  { id: "settings", label: "Settings", endpoint: "/api/settings", description: "Configure everything." },
];
