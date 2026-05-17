# Updates

v0.5.6 supports local update metadata only. Automatic downloads and installs are not implemented.

## Commands

```bash
./liuant update-check
./liuant update-info
./liuant update-config
```

## Settings

- `update_channel`: defaults to `local-mvp`
- `update_feed_url`: blank by default
- `auto_update_enabled`: false by default

`update-check` reads `release.json` and does not use the network.

## Future Work

- Signed update feed.
- Artifact signature verification.
- Manual download flow.
- Automatic update UX after signing is implemented.
