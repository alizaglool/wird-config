# wird-add-channel

A Cloudflare Worker that serves a small Arabic page and triggers the
`add-channel.yml` GitHub Actions workflow on `alizaglool/wird-config`.
The GitHub token lives only in the Worker; the browser never sees it.

## Deploy

```
npm install -g wrangler
wrangler login
```

Create a fine-grained GitHub token at
https://github.com/settings/personal-access-tokens — scoped to the repository
`alizaglool/wird-config` **only**, with the single permission
**Actions: Read and write**, and nothing else.

```
cd worker && wrangler secret put GITHUB_TOKEN
wrangler secret put ADD_PASSCODE
wrangler deploy
```

`wrangler deploy` prints the deployed URL. It looks like
`https://wird-add-channel.<subdomain>.workers.dev`.

Until both secrets exist the Worker is live but inert: `/` still serves the page
so the deploy can be checked visually, while `/add` and `/status` return
`503 {"ok":false,"error":"not_configured"}` and never call GitHub.

## Changing the passcode

```
wrangler secret put ADD_PASSCODE
```

Enter the new passcode when prompted. It takes effect on the next request; no
redeploy is needed.

## Changing the daily run limit

Edit `DAILY_RUN_LIMIT` under `[vars]` in `wrangler.toml`, then run
`wrangler deploy`. Each run costs roughly 372 YouTube API quota units out of
the 10,000/day pot, and the scheduled prefetch runs already consume 1,444/day.
