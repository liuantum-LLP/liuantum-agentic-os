# Liuant Local Installers

These scripts install Liuant Agentic OS for local MVP use. They do not install global packages, do not use `sudo`, and do not overwrite an existing `.env`.

## macOS

```bash
bash installer/install_macos.sh
```

## Linux

```bash
bash installer/install_linux.sh
```

## Windows

Run PowerShell from the project root:

```powershell
.\installer\install_windows.ps1
```

## What Installers Do

- Check Python version.
- Create `.venv`.
- Install Liuant in editable mode.
- Create workspace folders.
- Copy `.env.example` to `.env` only if `.env` does not already exist.
- Run `liuant repair`.
- Run `liuant doctor`.

## Uninstall

Uninstall scripts stop the local server and remove only `.venv`. They preserve `.env`, workspace outputs, backups, and local database files.

## Native Packaging

v0.5.6 includes a real Tauri scaffold, placeholder platform icons, and package-readiness scripts:

```bash
./installer/package_macos.sh
./installer/package_linux.sh
./installer/package_windows.ps1
```

They run release checks, desktop checks, and only attempt a Tauri build when required dependencies exist. They do not claim signed output unless signing is configured separately.

Additional desktop build helpers:

```bash
./liuant desktop icons-generate
./liuant desktop build-guide
scripts/build_desktop_macos.sh
scripts/build_desktop_linux.sh
scripts/build_desktop_windows.ps1
```
