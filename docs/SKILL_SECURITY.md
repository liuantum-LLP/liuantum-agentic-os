# Skill Security

Security model for the Liuant skill ecosystem.

## Core Principles

1. **Local-first**: Skills run locally, no cloud marketplace or sync
2. **Disabled by default**: Installed skills must be explicitly enabled
3. **Permission-gated**: Skills declare what they need; nothing is granted automatically
4. **Approval-required**: Critical permissions require explicit user approval
5. **Sandboxed execution**: Skills run in restricted context with no direct system access

## Security Rules

### Manifest Security
- Manifests cannot contain secret-like values (API keys, tokens, passwords)
- Manifests cannot contain suspicious absolute paths (/etc/, /usr/bin/, /root/)
- All required fields must be present and valid
- Unknown permissions cause validation failure

### Installation Security
- Skills are installed from local paths only
- No network download or marketplace
- Validation must pass before installation
- Duplicate skill IDs are rejected unless --upgrade is used

### Execution Security
- Disabled skills cannot be executed
- Missing permissions block execution
- Critical permissions must be approved before execution
- Filesystem access is restricted to workspace and skill directories
- No direct shell execution without explicit permission and approval
- No direct email/social publishing without approval gating
- No secret access by default

### Permission Model
| Risk Level | Auto-Granted | Approval Required |
|------------|--------------|-------------------|
| Low | Yes | No |
| Medium | Yes | No |
| High | Yes | Recommended |
| Critical | No | **Required** |

### Path Restriction
Skills can only access files within:
- Their own skill directory (`skills/installed/<skill_id>/`)
- The workspace directory

Any attempt to access paths outside these directories raises `PermissionError`.

### External Actions
Skills that produce external actions (email drafts, social posts, shell commands) must:
1. Declare the appropriate permission
2. Have the permission approved
3. Return actions in the output for approval gating
4. Not execute actions directly

## What Skills Cannot Do

- Access secrets without `secrets.read` permission and approval
- Execute shell commands without `tools.shell` permission and approval
- Make HTTP requests without `network.http` permission and approval
- Access files outside workspace/skill directories
- Send emails or publish to social media without approval
- Access provider API keys directly
- Modify system files or directories

## Auditing

- All skill installations are recorded in the registry
- Permission approvals are tracked
- Execution results include warnings and approval requirements
- Validation errors are reported before installation
