# Liuant Agentic OS v3.1.0 Release Notes

Welcome to Liuant Agentic OS v3.1.0. This milestone completes our transition into a fully comprehensive agentic desktop OS while maintaining strict adherence to our core safety and local-first principles.

## Summary
v3.1.0 introduces the **Browser & Desktop Automation Layer**, **Voice Wake Assistant Foundation**, and **Expansive Multi-Provider Support**. We've grown significantly without compromising on security: no marketplace servers, no forced cloud syncing, and zero implicit trust for external autonomous actions.

## Major Capabilities
- **Browser Automation Layer**: Safely drive Chrome/Chromium sessions (optional Playwright dependency).
- **Desktop Automation Layer**: Safely execute local scripts and open native applications.
- **Action Approval Queue**: All destructive/external automation is intercepted by a unified gatekeeper. You must click "Approve".
- **Voice Assistant Foundation**: Simulation-first voice support. Configure a custom assistant name and dispatch commands over simulated audio channels, with optional and experimental Web Speech API integration.
- **Extensive Model Support**: We now natively integrate with Amazon Bedrock, OpenRouter, Google Gemini, Ollama, LM Studio, OpenAI, Anthropic, Groq, Mistral, Together, and Fireworks.

## What Changed Since v3.0.0
This v3.1.0 release is primarily focused on final documentation polishing, installer packaging cleanup, and ecosystem readiness testing on top of the monumental changes delivered in the v3.0.0 cycle.
- **Documentation Overhaul**: Comprehensive updates across all README, Installation, and Security docs.
- **Installer & Packaging Validation**: Refined the `liuant sidecar` build process and ecosystem checks.

## Safety Model
Our commitment to your security is uncompromising:
- Autonomous external interactions (like booking flights or sending emails) remain intentionally physically disabled or strictly gated.
- Secrets are automatically redacted from all approval payloads and logs.
- Skills must be explicitly enabled by the user before executing.

## Known Limitations
Please see [Known Limitations](KNOWN_LIMITATIONS.md) for a comprehensive list. Most notably:
- Voice is simulation-first.
- Community builds are unsigned.
- Browser functionality is gated by approval.

## GitHub Release Asset Checklist
- `liuant-desktop_3.1.0_x64.dmg` (macOS Intel)
- `liuant-desktop_3.1.0_aarch64.dmg` (macOS Apple Silicon)
- `Source code (zip)`
- `Source code (tar.gz)`
