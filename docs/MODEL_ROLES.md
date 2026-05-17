# Model Roles — Liuant Agentic OS v1.1.0

Model Roles let you assign specific models to different tasks. Instead of using one model for everything, you can configure specialized models for thinking, coding, planning, and more.

## Roles

| Role | Purpose | Example Models |
|------|---------|----------------|
| **Default** | General chat, summaries, simple tasks | `gpt-4.1-mini`, `llama3.2` |
| **Thinking** | Deep reasoning, analysis, strategy, reviews | `deepseek/deepseek-reasoner`, `claude-3-5-sonnet` |
| **Coding** | Code generation, debugging, refactoring, tests | `qwen/qwen3-coder`, `claude-3-5-sonnet` |
| **Planning** | Roadmaps, task breakdowns, execution plans | `moonshotai/kimi-k2.5`, `gpt-4o` |
| **Fast** (optional) | Quick summaries, simple chat, low-cost | `llama3.2`, `gpt-4.1-mini` |
| **Fallback** (optional) | Used if selected role model is unavailable | `llama3.2` (local) |

## Configuration

### CLI

```bash
# View all role configurations
./liuant models roles

# Set a role
./liuant models role-set thinking --provider openrouter --model "deepseek/deepseek-reasoner"
./liuant models role-set coding --provider openrouter --model "qwen/qwen3-coder"
./liuant models role-set planning --provider openrouter --model "moonshotai/kimi-k2.5"
./liuant models role-set default --provider ollama --model "llama3.2"

# Test a role
./liuant models role-test thinking

# Reset a role
./liuant models role-reset thinking

# Reset all roles
./liuant models role-reset-all
```

### API

```
GET  /api/models/roles
POST /api/models/roles/set     { "role": "thinking", "provider": "openrouter", "model": "deepseek/deepseek-reasoner" }
POST /api/models/roles/test    { "role": "thinking" }
POST /api/models/roles/reset   { "role": "thinking" } or {} for all
```

### Settings UI

Go to **Settings → Model Roles** to view and configure all roles. Each role shows:
- Provider and model name
- Cloud ☁️ or local 🖥️ badge
- Cost warning for cloud providers
- Configuration status

## How Routing Works

The model router uses deterministic keyword patterns to classify tasks:

- **Coding**: `code`, `debug`, `fix error`, `implement`, `refactor`, `test`, `traceback`, etc.
- **Planning**: `roadmap`, `plan`, `strategy`, `schedule`, `milestone`, `break down`, etc.
- **Thinking**: `analyze`, `compare`, `decide`, `reason`, `architecture`, `pros and cons`, etc.
- **Default**: Everything else

No cloud AI is used for routing — it's fast and private.

## Fallback Behavior

If a role's model is unavailable:
1. Try the fallback role
2. Fall back to the default role
3. Return an error message if nothing is configured

## Discussion Mode

See [Discussion Mode](./DISCUSSION_MODE.md) for multi-model collaboration.
