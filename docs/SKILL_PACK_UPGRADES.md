# Skill Pack Upgrades

Skill packs can be upgraded to newer versions with a safe upgrade flow that includes backup, change detection, and rollback support.

## Upgrade Flow

1. **Preview** — Run `upgrade-plan` to see what will change
2. **Confirm** — Run `upgrade --confirm true` to apply
3. **Backup** — Previous version is backed up automatically
4. **Apply** — New pack replaces the old one
5. **Rollback** — Restore previous version if needed

## CLI Commands

### Preview Upgrade

```bash
./liuant skills pack upgrade-plan ./new-pack.liuantskillpack
```

Shows:
- Version change (from → to)
- Skills added
- Skills removed
- Skills changed
- Permission changes
- Risk level changes
- Whether permission re-approval is required

### Apply Upgrade

```bash
./liuant skills pack upgrade ./new-pack.liuantskillpack --confirm true
```

### Force Upgrade (same/lower version)

```bash
./liuant skills pack upgrade ./pack.liuantskillpack --confirm true --force true
```

### Rollback

```bash
./liuant skills pack rollback <pack_id> --confirm true
```

Restores the previous version from backup.

## Upgrade Plan Shape

```json
{
  "pack_id": "analytics-starter-pack",
  "from_version": "0.1.0",
  "to_version": "0.2.0",
  "skills_added": ["new-skill"],
  "skills_removed": ["old-skill"],
  "skills_changed": ["updated-skill"],
  "permission_changes": [
    {
      "skill_id": "updated-skill",
      "added": ["models.generate"],
      "removed": []
    }
  ],
  "risk_change": "low -> medium",
  "requires_permission_reapproval": true,
  "backup_path": "workspace/skills/packs/imported/analytics-starter-pack_backup_0.1.0"
}
```

## Safety Rules

- Upgrade requires same `pack_id`
- New version must be greater (unless `--force`)
- New pack is validated before upgrade
- Backup is created before applying changes
- Skills remain disabled by default after upgrade
- New permissions require approval before enable/run
- Rollback requires confirmation

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/skills/packs/upgrade-plan` | Preview upgrade |
| POST | `/api/skills/packs/upgrade` | Apply upgrade |
| POST | `/api/skills/packs/rollback` | Rollback to previous version |
