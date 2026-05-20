# Skill Permissions

Skills declare what resources they need access to. Permissions are gated by risk level.

## Permission Types

| Permission | Risk Level | Description |
|------------|------------|-------------|
| `filesystem.read` | Low | Read files within allowed directories |
| `workspace.read` | Low | Read workspace data |
| `usage.read` | Low | Read usage/cost data |
| `models.generate` | Medium | Generate text via model providers |
| `filesystem.write` | Medium | Write files within allowed directories |
| `workspace.write` | Medium | Write workspace data |
| `tools.browser` | Medium | Use browser automation |
| `tools.email_draft` | High | Create email drafts |
| `tools.social_draft` | High | Create social media drafts |
| `network.http` | High | Make HTTP requests |
| `tools.shell` | Critical | Execute shell commands |
| `secrets.read` | Critical | Read stored secrets |

## Risk Levels

| Level | Description | Approval Required |
|-------|-------------|-------------------|
| Low | Safe operations | No |
| Medium | Moderate risk | No |
| High | Significant risk | Recommended |
| Critical | Dangerous operations | **Required** |

## Critical Permissions

These permissions always require explicit approval:

- `secrets.read` — Access to stored secrets
- `tools.shell` — Shell command execution
- `network.http` — Outbound network requests
- `tools.email_draft` — Email draft creation
- `tools.social_draft` — Social media draft creation

## Approval Flow

```bash
# View skill permissions
./liuant skills permissions <skill_id>

# Approve specific permissions
./liuant skills approve-permissions <skill_id> --permissions perm1,perm2 --confirm true

# Enable skill (fails if critical permissions unapproved)
./liuant skills enable <skill_id>
```

## Security Rules

- Skills cannot access secrets by default
- Skills cannot access filesystem outside their folder and workspace without permission
- External actions require approval gating
- Filesystem paths are resolved and restricted to allowed directories
- No permission grants access to raw provider API keys
