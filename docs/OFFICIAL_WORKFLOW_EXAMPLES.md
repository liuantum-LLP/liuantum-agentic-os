# Official Workflow Examples

Liuant Agentic OS v2.6.0 includes official workflow examples that demonstrate practical use cases for combining multiple skills into step-by-step pipelines.

## Available Workflows

### 1. csv-analysis-report
**Purpose:** Read a CSV, summarize rows/columns/missing values, then generate a report review.

**Skills Used:**
- `csv-summary-skill`: Analyzes CSV structure and content
- `prompt-review-skill`: Reviews generated summaries

**Use Cases:**
- Quick data exploration
- Data quality checks
- Initial insights generation

**Location:** `examples/workflows/csv-analysis-report/`

---

### 2. prompt-improvement-review
**Purpose:** Review a prompt, improve clarity, and produce safety notes.

**Skills Used:**
- `prompt-review-skill`: Analyzes, improves, and checks prompts for safety

**Use Cases:**
- Crafting better prompts for AI
- Ensuring prompt safety
- Improving prompt specificity

**Location:** `examples/workflows/prompt-improvement-review/`

---

### 3. starter-greeting-workflow
**Purpose:** Run hello-skill and format the output as a simple workflow result.

**Skills Used:**
- `hello-skill`: Generates greeting messages

**Use Cases:**
- Learning workflow structure
- Testing workflow execution
- Basic input/output handling

**Location:** `examples/workflows/starter-greeting-workflow/`

---

### 4. analytics-pack-checkup
**Purpose:** Inspect local analytics pack, lint it, and produce a safe checklist.

**Skills Used:**
- `pack-inspection-skill`: Inspects pack structure
- `pack-lint-skill`: Lints for quality issues
- `prompt-review-skill`: Generates safety checklist

**Use Cases:**
- Pack quality maintenance
- Compliance verification
- Safety checklist generation

**Location:** `examples/workflows/analytics-pack-checkup/`

---

## Workflow Structure

Each workflow example includes:
- `workflow.json`: Workflow definition with steps, permissions, and metadata
- `README.md`: Usage documentation
- `sample_input.json`: Example input data
- `expected_output.json`: Expected output structure

## Usage

```bash
# List all workflows
liuant skills workflow list

# Preview a workflow
liuant skills workflow preview csv-analysis-report --input '{"csv_path":"workspace/data/sample.csv"}'

# Check permissions
liuant skills workflow permissions csv-analysis-report

# Run with confirmation
liuant skills workflow run csv-analysis-report --input '{"csv_path":"workspace/data/sample.csv"}'

# Dry run (no execution)
liuant skills workflow run csv-analysis-report --dry-run true --input '{"csv_path":"workspace/data/sample.csv"}'
```

## Discovery

Workflows are automatically discovered from:
- `examples/workflows/` (official examples)
- `examples/skill-packs/*/source/workflows/` (pack workflows)
- `workspace/skills/workflows/` (registered workflows)

## Safety

- Workflows do not run automatically after import
- Execution requires explicit user confirmation
- External actions remain approval-gated
- No secrets are stored in workflow definitions

## No Marketplace

Liuant does not have a marketplace server. All workflows are:
- Local-only
- Installed from local sources
- Manually discovered and installed

## No Cloud Sync

All workflow data remains on your local machine. No data is synced to cloud services.

## No Auto-Run

Workflows must be explicitly triggered via:
- CLI: `liuant skills workflow run <workflow_id>`
- Chat: "Run CSV analysis workflow"
- Desktop UI: Click "Run" button with confirmation

## Next Steps

- Explore the official workflow examples
- Create your own custom workflows
- Share workflows with your team
- Contribute workflows to the community
