# Unsigned Builds

v0.7.0 introduces a macOS code-signing and notarization pipeline, but unsigned builds remain the default. Liuant does not claim signed or notarized artifacts unless real signing/notarization succeeds.

## Commands

```bash
./liuant release artifacts
./liuant release unsigned-artifacts
./liuant release verify-artifacts
./liuant release checksum
```

## Frontend Bundle Only

After `npm run build`, files under `apps/desktop/dist` are frontend bundle artifacts. They are useful for QA and checksum tracking, but they are not native installers.

## Native Artifacts

Native artifacts are only reported when real files exist under Tauri release paths such as:

```text
apps/desktop/src-tauri/target/release/bundle/
```

When native artifacts exist, Liuant records:

- path
- platform
- artifact type
- checksum
- `signed=false`
- `notarized=false`
- `current_version_artifact` (artifact matching `app_version`)
- `stale_native_artifacts` (artifacts with different version)

## Signing Pipeline (v0.7.0)

macOS Developer ID signing and notarization is now supported via:

```bash
./liuant signing macos-sign --confirm true
./liuant signing macos-notarize --confirm true
```

However, unsigned builds remain the default. The `DO_SIGN=false` and `DO_NOTARIZE=false` defaults in `installer/package_macos.sh` ensure that signing is opt-in.

All existing unsigned commands (`unsigned-artifacts`, `verify-artifacts`, `unsigned-build-check`) continue to return `signed: false, notarized: false` — they are not affected by the signing pipeline.

Do not distribute unsigned builds as production-ready installers. Use the signing pipeline when distributing to users outside your development environment.
