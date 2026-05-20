# Hello Skill

A minimal starter skill for Liuant Agentic OS.

## Description

Greets the user with a personalized message. No permissions required.

## Usage

```bash
./liuant skills run hello-skill --input '{"message":"Liuant"}'
```

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | No | Name or message to greet (default: "World") |

## Output

```json
{
  "greeting": "Hello, Liuant! Welcome to Liuant Agentic OS.",
  "skill_id": "hello-skill",
  "permissions_used": []
}
```

## Permissions

None required.

## Risk Level

Low
