# Contributing to Liuant Agentic OS

## Local Setup

```bash
git clone <repo-url>
cd liuant_ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
pytest -q
```

## Desktop Frontend

```bash
cd apps/desktop
npm install
npm run typecheck
npm run build
npm run tauri:dev   # requires Rust/Cargo
```

## Running Tests

```bash
pytest -q                    # all tests
pytest -q tests/path.py      # specific file
```

## Coding Style

- Python: `snake_case` for functions/variables, `PascalCase` for classes.
- TypeScript: `camelCase` for functions/variables, `PascalCase` for components/types.
- No secrets, API keys, tokens, or private paths in code or commits.
- Keep external actions approval-gated.
- All new features must include tests.

## Branch Naming

- `feature/<short-description>` for new features.
- `fix/<short-description>` for bug fixes.
- `docs/<short-description>` for documentation.

## Pull Request Process

1. Run tests locally: `pytest -q`
2. Run frontend checks: `npm run typecheck && npm run build`
3. Ensure no secrets are included in the diff.
4. Update documentation if behavior changes.
5. Submit a PR with a clear description and checklist.

## Safety Rules

- **No auto-send.** Gmail sending, social publishing, Telegram auto-reply must remain approval-gated.
- **No secrets in logs.** Use the `mask_secret` helper.
- **No prompt injection bypass.** External messages (Telegram, webhooks) are untrusted input.
- **No cloud dependency for core routing.** The ChatIntentRouter uses deterministic pattern matching.
- **Signing/notarization is optional.** Community builds are unsigned and that is the default.
