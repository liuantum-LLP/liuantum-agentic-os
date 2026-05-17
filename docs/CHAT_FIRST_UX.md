# Chat-First UX in Liuant Agentic OS

Introduced in v0.6.3, hardened with a 384-test suite in v0.6.4.

The chat-first UX makes the Chat page the primary interface for configuring and controlling Liuant through natural language.

## How It Works

Users type requests in the Chat page. The message is sent to `/api/chat/message`, which routes through `ChatIntentRouter` (`runtime/chat/intent_router.py`). The router uses deterministic keyword and pattern matching to classify the intent and return a structured reply. No cloud AI provider is required for basic routing.

### Supported Intents

| Intent | Example | What Happens |
|---|---|---|
| `provider_setup` | "Set Kimi as default model" | Guides through provider configuration, collects API key, stores in SecretStore |
| `connector_setup` | "Connect Telegram" | Walks through connector credentials, validates settings |
| `agent_create` | "Create a marketing agent" | Collects agent name, tools, description; shows preview before creating |
| `automation_create` | "Every morning create a task list" | Prompts for schedule type, time, agent, task; shows preview before creating |
| `skill_install` | "Install HyperFrames skill" | Guides through registry skill installation |
| `memory_add` | "Remember my timezone is UTC+2" | Adds to memory store |
| `knowledge_search` | "Look up connector docs" | Searches knowledge base |
| `system_status` | "What's the system status?" | Returns current system overview |
| `approval_action` | "Show pending approvals" | Lists pending approval items |
| `release_status` | "What version is this?" | Shows version, signed/notarized status |
| `unknown` | Anything unrecognized | Suggests available actions |

## Examples

### "Connect Telegram"

```
You: Connect Telegram
Liuant: Let me help you set up the Telegram connector.
        I'll need a Telegram Bot Token.
        Please enter it now (it will be stored securely):

You: [enters token — masked in UI]
Liuant: Token received and stored securely.
        Would you like me to set up the webhook now? [Preview] [Confirm]
```

### "Create a marketing agent"

```
You: Create a marketing agent
Liuant: I'll help you create a marketing agent.
        What should its name be?

You: Content Creator
Liuant: Great. What tools should it use? (e.g., social, email, image)

You: social, image
Liuant: Here's a preview of your new agent:

  Name: Content Creator
  Tools: social, image
  Enabled: true

  [Confirm] [Cancel]
```

### "Every morning create a task list"

```
You: Every morning create a task list
Liuant: I'll set up a daily automation. What time in the morning?

You: 9:00
Liuant: Which agent should run this?

You: personal-assistant-agent
Liuant: Here's a preview of your automation:

  Name: Daily Task List
  Schedule: daily at 09:00
  Agent: personal-assistant-agent
  Task: Create my daily task list

  [Confirm] [Cancel]
```

### "Set Kimi as default model"

```
You: Set Kimi as default model
Liuant: I'll help you configure the Kimi provider.
        What's your Kimi API key? (it will be stored securely)

You: [enters key — masked in UI]
Liuant: Key stored. Kimi is now set as your default text provider.
        [Confirm]
```

### "Install HyperFrames skill"

```
You: Install HyperFrames skill
Liuant: HyperFrames skill is available in the registry.
        Run `hyperframes add <block-name>` from the command line,
        or use the Skills section in Settings to install it.

        Shall I show you available registry blocks? [Show Blocks]
```

## Secure Credential Collection

When chat requires a secret or token:

1. Chat asks for the value with a descriptive prompt.
2. The user types the value in a masked input field (bullets/asterisks shown, plain text never visible).
3. The value is stored in the encrypted local SecretStore.
4. After storage, only a redacted reference is shown or logged (e.g., `sk-...abc123`).
5. The raw value is never displayed again, never logged, and never sent to any external service.

## Confirmation and Preview Model

Any chat action that creates, modifies, or deletes resources requires:

1. **Collection phase**: Chat gathers all required fields through natural conversation.
2. **Preview phase**: A summary of what will be created/changed is displayed with key details.
3. **Confirmation phase**: The user must click "Confirm" or type a confirmation before the action executes.
4. **Execution phase**: The action is performed and a result summary is shown.

This applies to: agent creation, automation creation, provider setup, connector setup, and any resource modification.

## Safety Restrictions

- Chat cannot run shell commands or execute arbitrary code.
- Chat cannot send emails, publish social posts, or auto-reply to Telegram messages.
- Chat cannot delete resources without explicit confirmation.
- Chat cannot access or display stored secrets/tokens in plain text.
- Chat cannot modify security settings without additional authentication.
- Chat's deterministic router has no cloud AI dependency; AI enhancement is optional and off by default.

## Testing & Safety (v0.6.4)

The ChatIntentRouter is covered by a 384-test suite in `tests/test_chat_intent_router_v064.py`:

- **Intent detection**: Tests for all 11 intents with confirmed messages.
- **Confidence scoring**: Ensures known messages score > 0, unknown messages score 0.
- **Multi-match confidence**: Messages matching multiple patterns get higher scores.
- **Required fields**: Each intent that needs fields has `required_fields` populated correctly; secret fields are marked with `"secret": true`.
- **Preview generation**: Every response includes a `preview` block with a descriptive type.
- **Extraction helpers**: `_extract_connector`, `_extract_agent_role`, `_extract_memory_content`, `_extract_schedule`, `_extract_task`, `_extract_search_query` all tested.
- **execute_intent_action**: Error cases (missing required data, unknown intents) produce proper error responses.
- **Response structure invariants**: Every route response has `intent`, `status`, `message`, `preview`, `required_fields`.
- **15 safety tests**: Secrets masked in responses, prompt injection blocked, "send email now" and "publish social post now" never complete, all regex patterns compile, all secret-gated fields are marked properly.

## Deterministic Routing

The ChatIntentRouter uses simple keyword/pattern matching:

- Each intent handler defines activation patterns (e.g., `["connect", "telegram", "bot"]` for `connector_setup`).
- Patterns are matched case-insensitively across the user's message.
- When multiple intents match, the one with the most pattern matches wins.
- Unknown messages return a helpful response suggesting the closest matching intents.

This ensures chat works fully offline with zero cloud dependencies.
