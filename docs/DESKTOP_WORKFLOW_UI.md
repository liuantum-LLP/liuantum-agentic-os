# Desktop Workflow UI

Liuant Agentic OS v2.6.0 adds comprehensive workflow management to the desktop app, including workflow discovery, preview, permission review, dry-run, audit history, and more.

## Workflow Templates Section

The Settings page includes a **Workflow Templates** section that displays all available workflow examples and installed workflows.

### Workflow Cards

Each workflow card shows:
- **Workflow name**: Human-readable title
- **Workflow ID**: Unique identifier (e.g., `csv-analysis-report`)
- **Description**: Brief overview of what the workflow does
- **Source**: Location (official examples, pack, or workspace)
- **Required skills**: List of skills needed
- **Required permissions**: List of permissions required
- **Risk level**: Low/Medium/High based on permissions
- **Status**: Ready/Missing skills/Disabled skills/Missing permissions
- **Latest run status**: Last execution result if available

### Available Buttons

Each workflow card provides:
- **Inspect**: View detailed workflow structure
- **Preview**: See execution plan without running
- **Permissions**: Review required permissions
- **Dry Run**: Test execution without committing
- **Run**: Execute with confirmation dialog
- **View Audit**: Check run history and logs
- **View Run History**: See all past executions

## Workflow Preview Panel

When you click **Preview**, the panel shows:
- **Status**: Ready/Blocked/Missing skills/Disabled skills
- **Steps**: Step-by-step execution plan
- **Skill installed/enabled state**: For each step
- **Permissions required**: Aggregated across all steps
- **Input source**: User input or previous step output
- **Output key**: Where each step's result is stored
- **Warnings**: Any issues or missing dependencies
- **Blocked reason**: If workflow cannot run

**Important:** No skills are executed during preview.

## Workflow Permission Review Panel

When you click **Permissions**, the panel shows:
- **Permission**: Required permission name
- **Required by skills**: Which skills need each permission
- **Risk level**: Low/Medium/High for each permission
- **Approved**: Yes/No for each permission
- **Missing approval**: Yes/No for each permission

### Approval Buttons

- **Approve permissions**: Requires confirmation dialog
- **Refresh**: Reload permission status

**Important:** Critical permissions show strong warnings. Approval requires explicit confirmation.

## Dry-Run and Run Confirmation

### Dry Run

When you click **Dry Run**:
- Calls `POST /api/skills/workflows/{workflow_id}/run-dry`
- Shows execution plan
- Shows warnings
- **Does not execute skills**
- Does not modify any data

### Run

When you click **Run**:
1. Shows confirmation dialog with:
   - Workflow ID
   - Required permissions
   - External actions possible: Yes/No
   - Skills involved
2. Calls `POST /api/skills/workflows/{workflow_id}/run`
3. Shows result safely
4. If result has actions:
   - Shows `approval_required: true`
   - Sends actions to approval queue
   - Does not execute external actions directly

**Important:** Run requires confirmation. External actions are approval-gated.

## Workflow Audit / Run History Section

The audit/history section shows:
- **Latest runs**: Recent workflow executions
- **Workflow ID**: Which workflow was run
- **Run ID**: Unique execution identifier
- **Status**: Completed/Failed/Running/Pending
- **Duration**: Execution time
- **Step count**: Total steps
- **Completed steps**: Steps that finished
- **Failed step**: If any step failed
- **Warnings**: Any warnings during execution
- **Timestamp**: When execution started

### History Buttons

- **View details**: See full execution details
- **Export run**: Export run data (if API exists)
- **Rerun plan from failed step**: See how to resume from failure

**Important:** No secrets, raw prompts with secrets, file contents, API keys, or tokens are shown.

## URL Staged Import UI

The Skill Packs section includes a visible staged import flow for URL imports:

1. **URL input**: Enter the HTTPS URL
2. **Preview URL button**: Validate and preview the pack
3. **Show staged_id**: Unique identifier for staged pack
4. **Show validation result**: Pack structure and metadata
5. **Show pack metadata**: Name, version, author, etc.
6. **Show trust status**: Signed/Unsigned/Untrusted
7. **Show risk summary**: Permissions and security assessment
8. **Show dependencies**: Required skills and packages
9. **Import staged button**: Import with confirmation
10. **Install staged button**: Install with confirmation

### Warnings

- URL import is not a marketplace
- HTTPS required
- Skills remain disabled after install
- Review permissions before enable
- Unsigned/untrusted packs are marked

## Lint Fix Suggestions UI

The lint section shows:
- **Lint score**: Numeric quality score (0-100)
- **Grade**: Letter grade (A/B/C/D/F)
- **Issues**: List of quality issues
- **Recommendations**: Suggested improvements
- **Safe fix suggestions**: Templates that can be auto-generated

### Fix Buttons

- **Show fix suggestions**: Display available safe fixes
- **Apply safe fixes**: Apply with confirmation dialog

**Important Rules:**
- Do not modify code files
- Only safe fixes allowed (templates only)
- Confirmation required before applying

## Recommendation Ranking UI

The recommendation section shows:
- **Recommended pack/skill**: Name and ID
- **Score**: Matching score (0-100)
- **Reason**: Why this recommendation was made
- **Factor breakdown**: Explanation of scoring factors
- **Source**: Local catalog
- **Installed**: Yes/No
- **Risk summary**: Permissions and security assessment
- **Trust state**: Signed/Unsigned/Untrusted

### Recommendation Buttons

- **Preview install**: See what will be installed
- **Inspect**: View detailed pack information
- **Search catalog**: Find more related packages

**Important Rules:**
- Recommendations local-only
- No telemetry
- No external API calls
- No marketplace claims

## Safety

### No Marketplace

Liuant does not have a marketplace server. All workflows and packs are:
- Local-only
- Installed from local sources
- Manually discovered and installed
- No automatic downloads from internet

### No Cloud Sync

All workflow data remains on your local machine. No data is synced to cloud services.

### No Auto-Run

Workflows must be explicitly triggered via:
- CLI: `liuant skills workflow run <workflow_id>`
- Chat: "Run CSV analysis workflow"
- Desktop UI: Click "Run" button with confirmation

### External Actions Approval-Gated

All external actions require:
- Permission approval before enable
- Confirmation before run
- Explicit user consent

## Keyboard Shortcuts

- **Ctrl+P**: Quick open workflow
- **Ctrl+Shift+P**: Command palette with workflow commands
- **Esc**: Close panels

## Troubleshooting

### Workflow Not Found

- Ensure workflow is installed or in examples/workflows
- Run `liuant skills workflow list` to see available workflows
- Check workspace path in Settings

### Missing Skills

- Install required skills via Chat or CLI
- Run `liuant skills install <skill_id>`
- Check skill status in Settings > Skills

### Permission Denied

- Review permissions in workflow preview
- Enable required permissions in Settings > Security
- Confirm approval when prompted

### Run Failed

- Check workflow audit for detailed error
- Review failed step and dependencies
- Try dry-run to identify issues before running
