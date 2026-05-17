# Settings — Configuration Center

Introduced in v0.6.3, enhanced with helper text and empty states in v0.6.4.

## Section Overview

### 1. General
- **App name and version** display
- **Channel** (local-mvp)
- **Python version requirement**
- **Supported platforms**

### 2. Models & Providers
- **Configured providers** list with status (connected/missing key)
- **Default provider** per category (text, image, video, embedding)
- **Fallback provider** per category
- **Provider test** buttons
- *Advanced*: Custom API-compatible provider configuration

### 3. Connectors
- **Installed connectors** list (Gmail, Telegram, LinkedIn, X/Twitter)
- Each connector shows: status (connected/disconnected), last test result
- **Setup flow** for each connector
- **Enable/disable** connectors
- *Requires confirmation*: Disabling or removing a connector

### 4. Agents
- **Registered agents** list
- Each agent shows: name, tools, enabled/disabled, last run
- **Create agent** (also available via Chat)
- *Requires confirmation*: Deleting an agent

### 5. Automations
- **Scheduled automations** list
- Each automation shows: name, schedule, agent, next run, enabled/disabled
- **Create automation** (also available via Chat)
- **Run history** and log links
- *Requires confirmation*: Disabling or deleting an automation

### 6. Skills
- **Available registry skills**
- **Install status** per skill
- **Install/remove** skill buttons
- *Advanced*: Custom skill registry configuration

### 7. Memory & Knowledge
- **Memory entries** list with search
- **Knowledge sources** list with search
- **Add memory** / **Add knowledge** forms
- **Default embedding provider** configuration
- *Advanced*: RAG settings (enable/disable per run type)

### 8. Security
- **API token status** (generated/not generated)
- **Token rotation** button
- **Session records** list
- **Secret store status** (backend type, encryption)
- **Secret migration** tool
- **Audit log** access
- *Requires confirmation*: Token rotation, secret migration, clearing sessions

### 9. Desktop & Backend
- **Backend mode** selector (external_backend, managed_backend, bundled_sidecar)
- **Backend status** (reachable, process PID if managed)
- **Start/stop/restart** managed backend buttons
- **Connection info** (localhost:8765)
- **Dependency status** (Node, npm, Cargo, Rust, Rustup, Tauri)
- **Native build check** button
- *Requires confirmation*: Changing backend mode
- *Advanced*: Port configuration, custom backend URL

### 10. Release & Updates
- **Current version** display
- **Build report** viewer
- **Artifacts** list with checksums
- **Signed/notarized** status (always false in MVP)
- **Icon status** and **generate icons** button
- **macOS QA check** button
- **Update channel** and **check for updates** (local metadata only)
- *Advanced*: Release manifest details

All Settings sections also include:
- **Helper text**: A brief description below the section heading explaining the section's purpose.
- **Empty states**: Sections with no configured items display guidance messages pointing users to Chat for setup.

## Security-Related Settings

| Setting | Requires Auth | Requires Confirmation | Notes |
|---|---|---|---|
| API token generation | Yes | Yes | Refreshes all sessions |
| Token rotation | Yes | Yes | Invalidates existing tokens |
| Secret migration | Yes | Yes | Moves secrets between backends |
| Session clearing | Yes | Yes | Logs out all sessions |
| Backend mode change | Yes | Yes | Impacts desktop connectivity |
| Connector disable/remove | Yes | Yes | May interrupt active workflows |
| Agent deletion | Yes | Yes | Irreversible |
| Automation deletion | Yes | Yes | Irreversible |
| General settings view | No | No | Read-only access |

## API Endpoints

Settings are backed by the following API endpoints:

- `GET /api/settings` — List all settings sections with current values
- `GET /api/settings/:section` — Get values for a specific section
- `PUT /api/settings/:section` — Update a settings section
- Various existing endpoints for specific operations (e.g., `/api/desktop/backend-mode`, `/api/signing/status`)
