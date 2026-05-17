# Video Generation

Liuant v0.5.0 supports two video creation modes.

## Model-Based Mode

Model-based mode creates provider jobs through the Model Hub. Replicate Video is the first implemented provider path.

```bash
./liuant video generate "Liuant Agentic OS launch video" --mode model_based --provider replicate_video --model owner/model
./liuant video poll <job_id>
./liuant video download <job_id>
./liuant video cancel <job_id>
./liuant video export <job_id>
```

Replicate setup:

```text
REPLICATE_API_TOKEN=your_token
REPLICATE_VIDEO_MODEL=optional_default_model_or_version
```

Verification:

```bash
./liuant verify video
./liuant verify provider replicate_video
```

Verification checks token/model readiness and does not create a paid video generation by default.

If `REPLICATE_API_TOKEN` is missing, Liuant creates a local `video_jobs` record with `needs_provider_setup` and setup guidance. If no model is configured or passed, the job returns `needs_model_setup`.

Liuant does not fake video files. A local media file is only saved when a provider returns a valid output URL and the download succeeds.

## HyperFrames Skill Mode

HyperFrames mode is provider-independent and always available:

```bash
./liuant video storyboard "Liuant Agentic OS launch video" --mode hyperframes_skill
./liuant video package "Liuant Agentic OS launch video" --mode hyperframes_skill
```

It creates:

- concept
- storyboard
- scene breakdown
- shot list
- frame prompts
- on-screen text
- voiceover script
- CTA
- HTML/CSS video package plan
- render instructions

Status is a completed package, not a rendered video.

## Provider Job Lifecycle

Video jobs store:

- provider
- model
- status
- provider job ID
- provider status URL
- provider output URL
- local output path
- package path
- errors
- timestamps

Supported job commands:

```bash
./liuant video jobs
./liuant video job <job_id>
./liuant video poll <job_id>
./liuant video download <job_id>
./liuant video cancel <job_id>
```

## Safety

- No fake rendered output.
- No social upload or YouTube upload.
- No automatic publishing.
- Provider keys are never logged.
- Output downloads must use HTTPS.
- Allowed video extensions are `.mp4`, `.webm`, and `.mov`.
- Downloads are saved only inside `workspace/outputs/videos`.

## Roadmap

Runway, Pika, Luma, Kling, OpenAI Video, ComfyUI Video, and custom video APIs remain config-ready or provider-ready until their live API clients are implemented and tested.
