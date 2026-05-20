# Installation Guide

## Prerequisites
- **Python 3.11+**: We recommend Python 3.11 to 3.14. Always use the `python3` command (avoid `python` if it resolves to an older version).
- **Node.js 20+** and **npm**: Required for building the desktop React UI.
- **Rust / Cargo**: Required *only* if you are building the native Tauri desktop bundle.

## Step 1: Install the Backend
The backend serves as the core OS processing engine.

```bash
# Clone the repository
git clone https://github.com/liuantum-LLP/liuant-agentic-os.git
cd liuant-agentic-os

# Create a fresh virtual environment
python3 -m venv venv
source venv/bin/activate

# Install core dependencies natively
pip install -e .
```

### Optional: Browser Automation Dependency
To enable the advanced browser automation capabilities, install the extra dependencies.

```bash
pip install -e ".[browser]"
python3 -m playwright install chromium
```

## Step 2: Build the Desktop UI
The frontend UI allows you to interface visually with your agent.

```bash
cd apps/desktop
npm install
npm run build
```

## Step 3: Launch
Once built, you can start the development server or the sidecar:

```bash
cd ../..
./liuant start
```

*For bundled distributions, read our [Desktop Packaging Guide](DESKTOP_PACKAGING.md) to generate standalone executables.*

## Note on sidecar build and one-click-check
Ensure you test with one-click-check. For the sidecar build, refer to other docs.
