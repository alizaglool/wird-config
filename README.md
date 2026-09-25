# wird-config

Remote configuration for **Wird (وِرد)** — the curated sheikh channel list.

## sheikhs.json

```json
{
  "version": 1,
  "updatedAt": "YYYY-MM-DD",
  "channels": [
    { "id": "UC...", "name": "..." }
  ]
}
```

| Field | Rule |
|---|---|
| `version` | Integer. Bump on a breaking shape change. |
| `updatedAt` | ISO date. Informational. |
| `channels[].id` | YouTube channel id — must start with `UC` and be exactly 24 characters. |
| `channels[].name` | Curated display name. Overrides YouTube's `snippet.title`. |

## How the app reads it

- Fetched from `https://raw.githubusercontent.com/alizaglool/wird-config/main/sheikhs.json`
- Cached for 1 hour; `ETag` / `If-None-Match` makes an unchanged refresh a zero-byte 304.
- An empty `channels` array is rejected — it will not overwrite a good cache.
- On any failure the app falls back to its cached copy, then to a build-time seed.

## Editing

Commit to `main`. Installed apps pick the change up within the 1-hour TTL — no App Store release needed.

**This repository must stay public.** `raw.githubusercontent.com` on a private repo requires an auth token the app does not send.
