# Known Limitations (v3.1.0)

Liuant Agentic OS prioritizes safety and local-first execution. As part of this commitment to user security, several capabilities are either intentionally limited or strictly gated.

## Signatures and Releases
- **Community builds are unsigned**: Unless directly signed by the core maintainers, binary distributions and app bundles remain unsigned.
- **macOS security prompts**: Because macOS requires notarization for seamless execution, unsigned builds will trigger the "App cannot be opened" warning. To bypass, users must manually right-click the app bundle and select **Open**.

## Infrastructure
- **No Marketplace Server**: There is no central server to browse, download, or review skills and workflows. The ecosystem is fully distributed and peer-to-peer.
- **No Cloud Sync**: By default, no settings, histories, or logs are synchronized to any cloud service. You are fully responsible for backing up your own `workspace` directory.

## Automation & Voice
- **Browser automation is approval-gated**: Browser orchestration requires explicit permission and approval for any interactions to execute.
- **Playwright is optional**: The underlying browser dependency (Playwright) is optional. If not installed (`pip install -e ".[browser]"`), browser actions will safely degrade or prompt installation.
- **Search APIs require keys**: You must supply your own keys (e.g., Google, Bing, DuckDuckGo) for integrated search functionalities unless you are using the manual/fallback mode.
- **Voice is simulation-first**: Microphone and Voice configurations are set to *simulation-first* by default. Using actual browser SpeechRecognition hardware is currently experimental.
- **No always-listening production voice**: Liuant is not designed as a passive, always-listening device agent. Voice input requires explicit triggering.

## External Safety
- **No autonomous transactions**: Liuant will not autonomously submit web forms, send emails, post to social media, or purchase goods. All destructive or external-facing interactions route to the **Approval Queue**.
- **Skill packs carry local trust only**: Skill Packs are trusted locally by the user upon installation. There is no central authority verifying the safety of custom third-party packs.

## Models
- **Keys required for cloud models**: We do not provide centralized routing for cloud models; you must bring your own API keys for providers like Amazon Bedrock, OpenRouter, Gemini, OpenAI, or Anthropic.
- **Local models require existing backends**: Using local models requires an existing setup for **Ollama** or **LM Studio** actively running on your host machine.
