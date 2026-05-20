# Code Signing

**Code signing is completely optional for Liuant Agentic OS.** 

Community builds compiled from the source code are unverified and unsigned. The core philosophy of this OS relies on local-first transparency rather than centralized trust.

## Unsigned Builds
If you download or compile an unsigned build:
- **macOS**: Right-click the application bundle and select **Open** to bypass Gatekeeper.
- **Windows**: Accept the SmartScreen warning by clicking **More Info** -> **Run Anyway**.
- **Linux**: Mark the AppImage as executable (`chmod +x`).

## Signed Releases
Official binaries distributed on the GitHub Releases page are signed by the core maintainers to verify their origin.

To inspect the signing status of your local environment:
```bash
./liuant signing status
```

This will truthfully report whether your current executable has valid signatures attached.
