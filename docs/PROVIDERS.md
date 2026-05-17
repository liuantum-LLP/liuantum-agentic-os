# Liuant Provider Hub

Liuant Agentic OS v0.5.0 is multi-provider by design. OpenAI is one provider, not a fixed dependency.

## Categories

| Category | Purpose | Providers |
|---|---|---|
| `text` | Agents, planning, summaries, coding, docs | OpenAI, Anthropic, Gemini, OpenRouter, Groq, Mistral, Together, Fireworks, Ollama, LM Studio, custom OpenAI-compatible |
| `image` | Posters, thumbnails, social creatives | OpenAI Image, Stability, Replicate, Ideogram, Leonardo, ComfyUI, Automatic1111, custom image API |
| `video` | Video jobs and provider-ready packages | Runway, Pika, Luma, Kling, OpenAI Video, Replicate Video, ComfyUI Video, HyperFrames Skill, custom video API |
| `embedding` | Memory, knowledge base, and RAG | Local Hash Embedding, OpenAI Embeddings, Gemini, Cohere, Voyage, Ollama, local sentence-transformers |
| `speech_to_text` | Future transcription | OpenAI STT, local Whisper, Deepgram, AssemblyAI, Google Speech |
| `text_to_speech` | Future narration | OpenAI TTS, ElevenLabs, Azure, Google, Piper local, Coqui local |

## Commands

```bash
./liuant providers categories
./liuant providers list
./liuant providers list --category image
./liuant providers status
./liuant verify providers
./liuant verify text
./liuant verify image
./liuant verify video
./liuant providers show openai_image
./liuant providers test ollama
./liuant providers enable openrouter
./liuant providers disable openrouter
./liuant providers set-default image openai_image
./liuant providers set-model text gpt-4.1-mini
./liuant providers set-fallback text ollama
./liuant text generate "Write a caption" --provider openai
./liuant text generate "Write a caption" --provider ollama --model llama3.1
./liuant providers list --category embedding
./liuant embedding test local_hash_embedding
```

Old model commands still work and call the Model Hub internally:

```bash
./liuant models list
./liuant models status
./liuant models test openai
```

## Defaults And Fallbacks

Defaults are stored in SQLite settings:

- `default_text_provider`, `default_text_model`
- `default_image_provider`, `default_image_model`
- `default_video_provider`, `default_video_model`
- `default_embedding_provider`, `default_embedding_model`
- `default_stt_provider`, `default_stt_model`
- `default_tts_provider`, `default_tts_model`
- `fallback_text_provider`, `fallback_image_provider`, `fallback_video_provider`

Agents can optionally store provider preferences. If an agent does not choose a provider, Liuant resolves the global default for the task category.

## Cloud Providers

Cloud providers read keys from environment variables, `.env`, or `.env.local`. Raw keys are never returned by CLI/API/UI.

Example:

```text
OPENAI_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
```

## Local Providers

Local providers use configured base URLs:

- Ollama: `http://127.0.0.1:11434`
- LM Studio: `http://127.0.0.1:1234/v1`
- ComfyUI: `http://127.0.0.1:8188`
- Automatic1111: `http://127.0.0.1:7860`

The test command checks reachability only. Liuant does not claim a local provider works until the endpoint is reachable.

## Embedding Providers

v0.2.7 implements embeddings for:

- `local_hash_embedding`: deterministic local fallback, no network, default for local-first RAG.
- `openai_embedding`: real OpenAI embeddings when `OPENAI_API_KEY` is configured.
- `ollama_embedding`: local Ollama embedding endpoint when Ollama is reachable and a model is configured.

Gemini, Cohere, Voyage, and local sentence-transformers remain config-ready placeholders.

Knowledge and memory use `local_hash_embedding` by default. Users can explicitly choose a cloud embedding provider, but private indexed text is not sent to cloud providers by default.

## Current Limits

- Text generation is implemented for OpenAI, OpenRouter, Ollama, LM Studio, and custom OpenAI-compatible providers.
- OpenAI Image remains the implemented image provider path.
- Replicate Video is the first implemented video provider job path and is covered by verification. It supports setup-required/model-required states, prediction creation, polling, output URL tracking, safe download, and cancellation through mocked tests.
- Runway, Pika, Luma, Kling, OpenAI Video, ComfyUI Video, and custom video APIs are config-ready/provider-ready until their live clients are implemented.
- HyperFrames Skill mode is always available and creates useful markdown/HTML package plans without external keys.
- Gmail summarization can use the configured text provider through Model Hub, then falls back to a deterministic local summary if the provider is unavailable.
