# Desktop Icons

v0.7.2 includes the final brand icon set — a premium neural orbit mark with luminous core, orbiting agent nodes, and radial data rings. The icon set was generated offline using only local Python standard-library code.

## Files

Icons live in:

```text
apps/desktop/src-tauri/icons/
```

Expected files:

- `icon.svg`
- `32x32.png`
- `128x128.png`
- `128x128@2x.png`
- `icon.ico`
- `icon.icns`
- `Square30x30Logo.png`
- `Square44x44Logo.png`
- `Square71x71Logo.png`
- `Square89x89Logo.png`
- `Square107x107Logo.png`
- `Square142x142Logo.png`
- `Square150x150Logo.png`
- `Square284x284Logo.png`
- `Square310x310Logo.png`
- `StoreLogo.png`

## Generate

```bash
./liuant desktop icons-generate
./liuant desktop icons-check
```

The generator uses only local Python standard-library code and does not download assets.

## Verification

After regeneration, verify the full set:

```bash
./liuant desktop icons-check
./liuant desktop native-check
```

Do not use copyrighted images or unlicensed fonts.
