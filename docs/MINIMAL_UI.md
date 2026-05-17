# Minimal Desktop UI

Introduced in v0.6.3, enhanced with onboarding wizard in v0.6.4.

## Navigation Structure

The sidebar contains six items:

| Page | Purpose |
|---|---|
| Chat | Primary control interface; configure everything through natural language |
| Dashboard | System overview with live status cards |
| Agents | View and manage AI agents |
| Automations | View and manage scheduled automations |
| Knowledge | Browse knowledge sources and memory |
| Settings | Central configuration center (10 sections) |

## Why Advanced Pages Moved Into Settings

Previously, pages like Provider Setup, Connector Management, Skills, Memory, Security, and Release info each had their own top-level navigation entry. In v0.6.3, these are consolidated into Settings sections because:

- Most users interact with Providers, Connectors, and Skills only during initial setup.
- Chat is now the primary way to configure these items.
- Settings provides a complete, browsable configuration center for advanced users.
- The simpler navigation reduces cognitive load and fits better in a compact sidebar.

## Page Descriptions

### Chat
The default landing page and primary control surface. Type natural language requests to configure providers, connectors, agents, and automations. Chat handles secure credential collection, shows previews before making changes, and requires confirmation for all resource modifications.

### Dashboard
Shows live system status at a glance:
- Liuant version
- Backend mode and reachability
- Active agents count
- Pending approvals count
- Active automations count
- Configured providers
- Connected connectors

All cards have a refresh button and link to relevant configuration.

### Agents
Lists all registered agents with:
- Agent name and description
- Enabled/disabled status
- Available tools
Each agent name links to its detail page.

### Automations
Lists all scheduled automations with:
- Automation name
- Schedule description
- Agent assigned
- Next run time
- Enabled/disabled status

### Knowledge
Unified view of:
- Knowledge sources (files, texts added to the knowledge base)
- Memory entries (user preferences, task context, project facts)

### Settings
10-section configuration center (see `docs/SETTINGS.md` for details):

1. General
2. Models & Providers
3. Connectors
4. Agents
5. Automations
6. Skills
7. Memory & Knowledge
8. Security
9. Desktop & Backend
10. Release & Updates

## Onboarding Wizard (v0.6.4)

First-time users see a 6-step onboarding wizard before the main app:

1. **Welcome** — Introduction to Liuant Agentic OS
2. **Backend Mode** — Choose external_backend or managed_backend
3. **Connect a Provider** — Guidance to set up AI provider via Chat
4. **Create an Agent** — Guidance to create first agent via Chat
5. **Create an Automation** — Guidance to set up recurring tasks via Chat
6. **Connect Services** — Optional Gmail/Telegram/LinkedIn/X setup via Chat

The wizard is skippable at any step via "Skip all — take me in". Once completed or skipped, it does not reappear (state persisted in localStorage).

## Offline and Auth States

The App shell handles three states:

- **Backend reachable, authenticated**: Full UI with all pages.
- **Backend reachable, not authenticated**: Login modal overlay. User enters API token from `./liuant auth token`.
- **Backend not reachable**: Offline banner with `./liuant start` instructions and retry button.

The sidebar footer shows:
- Backend connection status (green/gray indicator)
- Active page indicator
- Version badge

## Preserved Functionality

All existing CLI commands, API endpoints, backend features, and workflows remain fully functional. The minimal UI is a new desktop frontend shell that communicates with the same backend through the same API endpoints.
