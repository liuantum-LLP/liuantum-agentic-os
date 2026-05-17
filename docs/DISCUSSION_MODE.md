# Discussion Mode — Liuant Agentic OS v1.1.0

Discussion Mode lets multiple model roles collaborate on a single response. Each model gives an independent answer, reviews others, and a final model synthesizes the best response.

## How It Works

1. **Task Classification**: Your message is classified to determine relevant roles.
2. **Role Selection**: Based on the task, appropriate roles are selected:
   - Coding tasks → Coding + Thinking
   - Planning tasks → Planning + Thinking
   - Analysis tasks → Thinking + Planning
3. **Round 1**: Each role gives an independent answer.
4. **Round 2+**: Each role reviews and improves upon others' answers.
5. **Final Synthesis**: A designated role combines the best insights into a final answer.

## Configuration

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `discussion_mode_enabled` | `false` | Enable/disable discussion mode |
| `discussion_mode_default_rounds` | `2` | Default number of discussion rounds |
| `discussion_mode_max_rounds` | `4` | Hard cap on rounds |
| `discussion_mode_final_role` | `thinking` | Role that synthesizes the final answer |

### CLI

```bash
./liuant models discussion-status
./liuant models discussion-set discussion_mode_enabled true
./liuant models discussion-set discussion_mode_default_rounds 3
```

### API

```
GET  /api/models/discussion
POST /api/models/discussion/set  { "key": "discussion_mode_enabled", "value": "true" }
POST /api/chat/discussion        { "message": "...", "roles": ["thinking", "planning"], "rounds": 2 }
```

### Chat UI

- Toggle **Discussion Mode** on/off in the chat input area
- Select number of rounds (1-4)
- View discussion transcript in expandable summary
- See role chips, warnings, and cost notes

## Safety

### Secret Redaction
- API keys, tokens, passwords are automatically redacted before sending to models
- Pattern matching detects common secret formats

### Cost Warnings
- Discussion mode uses multiple model calls per round
- Cloud providers incur costs — warnings are shown
- Local models have no additional cost

### Restrictions
- Discussion is text-only
- No tools/external actions run during discussion
- External actions still require approval after final answer
- Max rounds capped at 4 (hard limit)

### Hidden Reasoning Protection
- Transcript contains concise role outputs, not raw chain-of-thought
- Uses "analysis summary" and "review notes" format
- Final answer is synthesized, not a copy of any single model's reasoning

## Cost Examples

| Configuration | Rounds | Model Calls | Cost Impact |
|--------------|--------|-------------|-------------|
| 2 roles, 2 rounds, all cloud | 2 | 4 + 1 synthesis | 5 cloud calls |
| 3 roles, 2 rounds, all local | 2 | 6 + 1 synthesis | Free |
| 1 role, 1 round | 1 | 1 + 1 synthesis | 2 calls |

## Examples

### Plan a Product Launch
```
User: "Plan my Liuant launch strategy"
Roles: planning + thinking
Rounds: 2
Result: Structured launch plan with strategic analysis
```

### Fix a Python Error
```
User: "Fix this error: TypeError: 'NoneType' object is not iterable"
Roles: coding + thinking
Rounds: 2
Result: Code fix with explanation of root cause
```

### Compare Strategies
```
User: "Compare Liuant vs OpenClaw for local-first AI"
Roles: thinking + planning
Rounds: 2
Result: Comprehensive comparison with recommendations
```
