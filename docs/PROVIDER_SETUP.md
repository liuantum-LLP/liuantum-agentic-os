# Provider Setup

The MVP checks environment variables and returns provider-ready prompts or storyboards when credentials are not configured.

## Model Providers

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `REPLICATE_API_TOKEN`
- `STABILITY_API_KEY`

## Image Providers

- OpenAI image generation: `OPENAI_API_KEY`
- Stability AI: `STABILITY_API_KEY`
- Replicate: `REPLICATE_API_TOKEN`
- ComfyUI: `COMFYUI_URL`
- Automatic1111: `AUTOMATIC1111_URL`

## Video Providers

- OpenAI Sora API where available: `OPENAI_API_KEY`
- Runway: `RUNWAY_API_KEY`
- Pika: `PIKA_API_KEY`
- Luma: `LUMA_API_KEY`
- Kling: `KLING_API_KEY`
- Replicate video models: `REPLICATE_API_TOKEN`
- Local ComfyUI video workflows: `COMFYUI_URL`

Provider availability changes often, so production integrations should remain provider-based rather than hardcoded to a single service.
