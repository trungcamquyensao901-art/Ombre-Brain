# Ombre Brain Cloud Deploy

This repo is ready for Docker-based cloud deployment. The recommended simple path is Zeabur with persistent storage.

## Zeabur Settings

Create a new service from your GitHub repo. Zeabur should detect the `Dockerfile` automatically.

Use these environment variables:

```env
OMBRE_TRANSPORT=streamable-http
OMBRE_BUCKETS_DIR=/app/buckets
OMBRE_API_KEY=<paste in Zeabur, do not commit>
OMBRE_BASE_URL=https://api.deepseek.com/v1
OMBRE_DEHYDRATION_MODEL=deepseek-chat
OMBRE_EMBEDDING_ENABLED=false
OMBRE_DASHBOARD_PASSWORD=<choose a strong password>
```

Add persistent storage:

```text
Mount path: /app/buckets
Size: 1 GB is enough for a small personal memory store
```

Expose HTTP port:

```text
Port: 8000
Protocol: HTTP
```

After deployment, the dashboard is:

```text
https://<your-zeabur-domain>/dashboard
```

The MCP endpoint is:

```text
https://<your-zeabur-domain>/mcp
```

## Migrating Local Memories

This workspace has a prepared migration archive:

```text
C:\Users\45842\Documents\Codex\2026-05-30\github-https-github-com-p0luz-ombre\outputs\ombre-buckets-migration.zip
```

Upload or extract it into the cloud volume at `/app/buckets`. It contains only bucket files, not `.env` or API keys.

Expected layout after extraction:

```text
/app/buckets/permanent/...
/app/buckets/dynamic/...
/app/buckets/archive/...
```

## Claude Connector

In Claude Desktop, add a custom connector using:

```text
https://<your-zeabur-domain>/mcp
```

If Claude asks for tool permissions, allow the Ombre Brain tools you want to use.

## Notes

- Keep `OMBRE_API_KEY` only in the cloud provider's environment variable panel.
- Keep persistent storage mounted before importing memories, otherwise redeploys can erase bucket files.
- `OMBRE_EMBEDDING_ENABLED=false` is intentional for DeepSeek-only setup. Turn it on only after adding a real embedding API.
