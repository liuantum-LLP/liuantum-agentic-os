# Liuant Agentic OS

**Local-first open-source Agentic OS for voice, browser automation, desktop automation, workflows, skills, and multi-model AI.**

Liuant Agentic OS is a robust desktop agent platform that operates locally, providing absolute privacy and control over your AI assistants. By design, no external actions happen without your explicit approval, keeping you safe while orchestrating complex automations.

## Feature Summary
- **Model Roles**: Distinct roles for thinking, coding, planning, fast tasks, and fallbacks.
- **Multi-provider AI**: Bring your own keys. Supports Amazon Bedrock, OpenRouter, Google Gemini, OpenAI, Anthropic, Groq, Mistral, Together, and Fireworks.
- **Local AI Support**: Out-of-the-box support for Ollama and LM Studio.
- **Voice Wake Assistant Foundation**: Simulation-first voice wake system, ensuring microphone requests remain opt-in and under control.
- **Browser Automation**: Safely automate browser tasks with granular approvals.
- **Desktop Automation**: Open applications, run scripts, and inspect local environments safely.
- **Skills & Skill Packs**: Expand capabilities by creating or installing localized skill sets.
- **Workflows**: Multi-step orchestrated pipelines that combine several skills sequentially.
- **Backup/Restore**: Keep your agent's memory, settings, and workflows safely backed up locally.
- **Usage/Cost Tracking**: Built-in tracking to help monitor local and cloud AI consumption.
- **Provider Health**: Diagnostic suite to measure model and API availability.
- **Approval Queue**: Centralized gatekeeper ensuring no critical action occurs without explicit user consent.

## Safety First
Liuant Agentic OS is built on a foundation of zero implicit trust:
- **Local-first**: All configurations, settings, memory, and code exist strictly on your local machine.
- **No cloud sync by default**: You decide if and when to backup data; no implicit cloud syncing.
- **No marketplace server**: Skills and workflows are distributed directly, ensuring no centralized surveillance.
- **Skills disabled by default**: Newly imported skills require explicit user enablement.
- **Browser/Desktop actions approval-gated**: Actions involving external side-effects trigger the Approval Queue.
- **No autonomous interactions**: No auto-submit, auto-purchase, auto-publish, or auto-send. You remain the final decider.
- **Secrets redacted**: All secrets are heavily redacted from queues and logs to prevent credential leakage.

## Quick Start
```bash
# Clone the repository
git clone https://github.com/liuantum-LLP/liuant-agentic-os.git
cd liuant-agentic-os

# Create a virtual environment and install backend natively
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Launch the backend
./liuant start
```

## Desktop Setup
```bash
cd apps/desktop
npm install
npm run build
npm run dev # or npm run tauri dev
```

## Sidecar Setup
If you want to bundle the backend with the Tauri app using PyInstaller:
```bash
./liuant sidecar build
./liuant sidecar status
```

## Provider Setup Summary
You can check or configure providers natively from the CLI:
```bash
./liuant models providers
./liuant providers openrouter setup-guide
./liuant providers profile-test lmstudio
```

## Examples

### Voice Simulation
Voice wake and commands are disabled by default. You can simulate interaction without granting microphone access:
```bash
./liuant voice name set "Liu"
./liuant voice simulate "Hey Liu, list workflows"
```

### Browser Automation
Browser automation is off by default. After enabling it in settings, actions get sent to the Approval Queue:
```bash
./liuant browser status
# When requested by an agent, check queue:
./liuant approvals list
```

### Workflows
Preview and execute multi-step routines safely:
```bash
./liuant skills workflows list
./liuant skills workflows preview example-workflow
./liuant skills workflows run example-workflow --confirm true
```

## Known Limitations
Please review the [Known Limitations](docs/KNOWN_LIMITATIONS.md) document to fully understand the current release scope.

## License and Startup
This is released under the MIT License. Use one-click-check for testing one-click startup.
