# Agent Runtime — Liuant Agentic OS v1.3.0

The agent runtime executes agent tasks with model role resolution, streaming support, and safety controls.

## Agent Role Inference

Each agent type has an inferred model role:

| Agent | Inferred Role | Purpose |
|-------|--------------|---------|
| `coding-agent` | `coding` | Code generation, debugging, refactoring |
| `brand-strategist-agent` | `planning` | Brand strategy, positioning, campaigns |
| `automation-builder-agent` | `planning` | Automation definitions, workflows |
| `email-assistant-agent` | `thinking` | Email drafting, analysis |
| `social-media-manager-agent` | `planning` | Content calendars, post planning |
| `video-creator-agent` | `planning` | Storyboards, scripts, scene planning |
| `image-creator-agent` | `default` | Image prompts, poster copy |
| `content-creator-agent` | `planning` | Campaign planning, content packages |
| `marketing-agent` | `planning` | Marketing plans, ad copy |
| `tutor-agent` | `thinking` | Lesson plans, quizzes, assignments |
| `business-analyst-agent` | `thinking` | BRD/FRD outlines, user stories |
| `sales-agent` | `planning` | Sales scripts, follow-ups |
| `customer-support-agent` | `default` | FAQ, support replies |
| `front-desk-management-agent` | `default` | Enquiry replies, call scripts |
| `personal-assistant-agent` | `default` | Daily plans, task lists |
| `hr-agent` | `default` | Job descriptions, interview questions |

## Agent Run Output

```json
{
  "agent_slug": "coding-agent",
  "prompt": "Fix this Flask route",
  "status": "completed",
  "result": {
    "summary": "...",
    "model_role_used": "coding",
    "provider_used": "openrouter",
    "model_used": "qwen/qwen3-coder",
    "fallback_used": false,
    "discussion_mode_used": false,
    "provider_routing": { ... },
    "approval_required_for_external_actions": true
  }
}
```

## CLI Usage

```bash
# Run agent with default role
./liuant agents run coding-agent "Fix this Flask route"

# Override model role
./liuant agents run coding-agent "Fix this Flask route" --model-role coding

# Enable discussion mode
./liuant agents run brand-strategist "Plan launch" --discussion

# Stream response
./liuant agents run coding-agent "Fix this error" --stream
```

## Safety

- **No direct email sending**: Agents must not send email directly
- **No social publishing**: Agents must not publish to social media directly
- **Draft-only outputs**: All action-producing outputs go to approval queue
- **No secrets in logs**: Agent runs store safe summaries, not full prompts
- **Approval gating**: External actions require explicit user approval

## Automation Model Role

Automations store and display:
- `model_role`: The role used for generation
- `provider/model`: Resolved at runtime
- `discussion_mode_enabled`: Whether discussion is active
- `discussion_roles`: Roles used in discussion
- `discussion_rounds`: Number of rounds
- `cloud_cost_warning`: Warning if cloud providers are used

### Automation Creation Preview

```json
{
  "name": "daily-report",
  "model_role": "planning",
  "provider": "openrouter",
  "model": "moonshotai/kimi-k2.5",
  "discussion_mode_enabled": false,
  "cloud_cost_warning": true,
  "approval_gating": true
}
```

## Streaming

See [STREAMING.md](./STREAMING.md) for streaming details.
