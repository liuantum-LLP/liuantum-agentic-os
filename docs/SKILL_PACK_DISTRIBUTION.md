# Skill Pack Distribution

This document describes how to create, share, and install skill packs for Liuant Agentic OS.

## Creating a Pack

### From Installed Skills

```bash
./liuant skills pack export \
  --skills hello-skill,csv-summary-skill \
  --pack-id my-pack \
  --name "My Skill Pack" \
  --version 0.1.0 \
  --output ./my-pack.liuantskillpack
```

### From Source Directory

1. Create a source directory with the pack structure:
   ```
   my-pack/
     skill-pack.json
     skills/
       hello-skill/
         skill.json
         skill.py
         README.md
     README.md
   ```

2. Generate checksums:
   ```bash
   python3 examples/skill-packs/build_packs.py
   ```

3. The script creates `my-pack.liuantskillpack` in the parent directory.

## Sharing Packs

Skill packs are self-contained `.liuantskillpack` files that can be shared via:

- File transfer (USB, AirDrop, etc.)
- Email attachment
- Git repository (source folder preferred over binary ZIP)
- Local network share

**Important:** There is no online marketplace or cloud sync. Packs are local-first.

## Installing a Pack

### From File

```bash
./liuant skills pack inspect ./path/to/pack.liuantskillpack
./liuant skills pack validate ./path/to/pack.liuantskillpack
./liuant skills pack install ./path/to/pack.liuantskillpack
```

### From Catalog

```bash
./liuant skills catalog
./liuant skills catalog install analytics-starter-pack
```

### From Chat

Say:
- "Install analytics starter pack"
- "Import hello starter pack"
- "Search catalog for analytics skills"

## Community Packs

In the future, a community pack submission system may allow sharing packs publicly. For now:

1. Create your pack source folder
2. Include a `README.md` with usage instructions
3. Share the source folder or `.liuantskillpack` file
4. Recipients validate before installing

## Pack Versioning

- Use semver-like versions (e.g., `0.1.0`, `1.0.0`)
- Increment version when adding/modifying skills
- `liuant_min_version` specifies minimum Liuant version required
- Upgrade existing packs by installing the new version (duplicate skill warning shown)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid ZIP archive" | File is corrupted or not a ZIP |
| "skill-pack.json not found" | Pack structure is incorrect |
| "Checksum mismatch" | File was modified after creation |
| "Secret-like values found" | Remove API keys/tokens from pack files |
| "Skill already installed" | Use `--upgrade` or uninstall first |
| "Critical permissions not approved" | Approve permissions before enabling |
