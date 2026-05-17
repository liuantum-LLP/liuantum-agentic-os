# Liuant Agentic OS Desktop

This is the v0.5.5 Tauri + React + TypeScript desktop shell.

It connects to the existing local Liuant backend. It does not start a sidecar backend yet.

Default backend:

```text
http://127.0.0.1:8765
```

Start the backend separately:

```bash
./liuant start 8765
```

Then run desktop dev mode:

```bash
cd apps/desktop
pnpm install
pnpm run typecheck
pnpm run build
pnpm tauri dev
```

If `pnpm` is unavailable, `npm install`, `npm run typecheck`, `npm run build`, and `npm run tauri:dev` are valid fallbacks.

Native Tauri commands require Rust/Cargo. If Cargo is missing, the frontend build can still pass while native artifacts remain unavailable.

Builds are unsigned and not notarized until signing configuration is added.
