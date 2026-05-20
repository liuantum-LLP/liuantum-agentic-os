# Prompt Review Skill

Review and improve prompts with clarity scoring and safety analysis.

## Description

Analyzes a prompt and provides:
- Clarity score (0-100)
- Safety notes
- Improved prompt draft

## Permissions

- `models.generate` - Required for full model-assisted review

## Usage

```bash
./liuant skills install ./examples/skills/prompt-review-skill
./liuant skills approve-permissions prompt-review-skill --permissions models.generate --confirm true
./liuant skills enable prompt-review-skill
./liuant skills run prompt-review-skill --input '{"prompt":"Write a story about AI"}'
```

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| prompt | string | Yes | The prompt to review |

## Output

```json
{
  "prompt": "Write a story about AI",
  "clarity_score": 65,
  "safety_notes": ["No obvious safety concerns detected."],
  "improved_prompt": "Write a story about AI.",
  "setup_needed": false
}
```

## Model Unavailable

If no model provider is configured, the skill returns:
- `setup_needed: true`
- Honest message about configuration requirement
- No fake or hallucinated analysis

## Risk Level

Medium (requires models.generate permission)
