# Screenshots and Demo Guide

When preparing promotional material or demonstrations for Liuant Agentic OS, refer to this guide to highlight our core capabilities while emphasizing safety.

## Required Screenshot Checklist
Before publishing a release, ensure you have captured up-to-date screenshots of the following views:
- [ ] **Chat Interface**: Show an active session with an agent.
- [ ] **Model Roles Settings**: Highlight the breakdown of thinking, coding, and fallback roles.
- [ ] **Provider Settings**: Show the rich multi-provider configuration pane (Bedrock, Ollama, etc.).
- [ ] **Voice Settings**: Highlight the simulation-first configuration and assistant naming.
- [ ] **Browser Automation Settings**: Show that automation is gated and defaults to off.
- [ ] **Desktop Automation Settings**: Highlight safe-app lists and gating mechanics.
- [ ] **Approval Queue**: Capture an active pending request (e.g., waiting to open a URL).
- [ ] **Skills & Skill Packs**: Show the directory of installed capabilities.
- [ ] **Workflows (List & Preview)**: Demonstrate the step-by-step preview of an orchestration.
- [ ] **Usage & Cost Dashboard**: Display token and estimated cost visualizations.
- [ ] **Backup & Restore**: Show the local-first manual backup interface.

## Standard Demo Script
Follow this flow for video demonstrations or conference talks:

1. **Start Backend**: Show the CLI `./liuant start` firing up instantly.
2. **Open Desktop**: Launch the React/Tauri app and demonstrate fast load times.
3. **Show Chat**: Say a quick hello to the agent and receive a rapid response.
4. **Show Providers**: Pivot to the settings to illustrate how easily one can switch from OpenAI to a local Ollama model.
5. **Show Voice Simulation**: Use `./liuant voice simulate "Hey Liu, list workflows"` to demonstrate voice interactions without needing live microphones.
6. **Show Browser Automation Preview**: Ask the agent to summarize a webpage.
7. **Show Approval Queue (Browser)**: Explicitly show the browser action pausing in the Approval Queue, emphasizing that the system waited for the user.
8. **Show Desktop Automation (Safe Apps)**: Ask the agent to open the Terminal and explicitly approve the action in the queue.
9. **Show Workflow Preview**: Run `./liuant skills workflows preview example-workflow` to show how complex pipelines are safely dry-run.
10. **Show Backup**: Manually trigger a backup to emphasize that data isn't secretly synced to the cloud.
11. **End with Local-First Safety**: Reiterate that Liuant requires zero marketplace servers, zero cloud accounts (beyond your chosen LLM providers), and offers absolute user control over external actions.
