# Skill Pack Base64 Import/Export

Small skill packs can be encoded as base64 text for easy sharing via clipboard, email, or chat.

## Size Limit

Default: **5 MB**. Packs larger than this cannot be encoded.

## CLI Commands

### Encode a Pack

```bash
./liuant skills pack encode ./pack.liuantskillpack --output pack.txt
```

### Decode a Pack

```bash
./liuant skills pack decode pack.txt --output decoded.liuantskillpack
```

### Import from Base64

```bash
./liuant skills pack import-base64 pack.txt
```

Decodes and imports in one step. Validates the decoded pack before import.

### Export Skills as Base64

```bash
./liuant skills pack export-base64 analytics-starter-pack --skills csv-summary-skill,prompt-review-skill --output analytics-pack.txt
```

## Safety Notes

- **Base64 is not encryption** — Anyone with the text can decode the pack
- Decoded packs are validated before import
- Checksums and signatures are preserved
- Imported skills are disabled by default
- No skills run during import

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/skills/packs/encode` | Encode pack to base64 |
| POST | `/api/skills/packs/decode` | Decode base64 to pack |
| POST | `/api/skills/packs/import-base64` | Decode and import |
