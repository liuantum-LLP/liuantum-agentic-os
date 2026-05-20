# Prompt Improvement Review Workflow

Analyze and improve prompts for better AI responses while checking for safety issues.

## Overview

This workflow helps you craft better prompts by analyzing your original prompt, suggesting improvements for clarity and effectiveness, and performing safety checks to ensure your prompt is appropriate.

## Skills Used

- `prompt-review-skill`: Analyzes prompts, suggests improvements, and performs safety checks

## Installation

This workflow is part of the official Liuant workflow examples. No additional installation required.

## Usage

```bash
liuant skills workflow preview prompt-improvement-review --input '{"prompt_text":"Write a tweet about AI"}'
liuant skills workflow permissions prompt-improvement-review
liuant skills workflow run prompt-improvement-review --input '{"prompt_text":"Write a tweet about AI"}'
```

## Permissions

This workflow requires no special permissions. It operates on text only.

## Input

```json
{
  "prompt_text": "Write a tweet about AI"
}
```

## Output

The workflow produces:
- `analysis`: Detailed analysis of your original prompt including clarity, specificity, and structure
- `improved_prompt`: Suggested improved version of your prompt
- `safety_notes`: Safety assessment with any concerns or recommendations

## Example

```bash
liuant skills workflow run prompt-improvement-review --input '{"prompt_text":"Create a marketing post for our new product"}'
```

## Notes

- The workflow focuses on making prompts clearer and more effective
- Safety checks help identify potentially problematic content
- Improvements are suggestions, not requirements
