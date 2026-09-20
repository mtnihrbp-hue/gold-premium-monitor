# Cloudflare Worker: Telegram Trigger

`telegram-trigger.js` mirrors the worker deployed on Cloudflare. Nothing in this
repository executes it. It is kept here so the deployed behaviour is reviewable,
diffable and recoverable.

**Edit here first, then paste into the Cloudflare dashboard.** The copy in this folder
drifted a full generation behind the deployed worker once already — different event
style, different variable names — which made it worse than having no copy at all,
because a reader would trust it.

## What it does

1. Receives webhook POST requests from Telegram
2. Validates the chat ID against `TELEGRAM_CHAT_ID`
3. Handles `Update`, `Status`, `start` / `help`
4. `Update` triggers `gold-monitor.yml` via `workflow_dispatch` on `TARGET_REF`
5. `Status` reports the newest run of that workflow on that branch

## The branch ref

```js
const TARGET_REF = "SP-C";
```

`workflow_dispatch` runs the workflow file **and the application code** from this ref.
It decides which version of the system answers a user.

This is the single most important line in the file. It pointed at `main` while active
development ran on `SP-C`, so `/Update` returned the previous message format while the
hourly scheduled runs returned the current one — the same system answering in two
different voices depending on how it was invoked.

**cron-job.org carries the same value** in its own request body (`{"ref": "...",
"inputs": {"mode": "analyze"}}`). The two must move together. Both return to `main`
when SP-C merges; see the merge checklist in `SP_C_HANDOFF.md`.

## Wings

The worker sends **no inputs**. `gold-monitor.yml` declares `mode` with a default of
`update`, which GitHub applies, so `SCHEDULED_RUN` stays `false` and a user command
takes the Live Wing path.

Only cron-job.org sends `inputs.mode = "analyze"`, which is what sets
`SCHEDULED_RUN=true` and runs the Analysis Wing. This is how the two wings stay
separate across a single workflow file.

## Environment variables

Set in the Cloudflare Workers dashboard (Settings → Variables):

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | Classic PAT with `repo` scope. Fine-grained tokens do not work. |
| `GITHUB_REPO` | **Full** path, `owner/repo` — e.g. `mtnihrbp-hue/gold-premium-monitor` |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | Numeric chat ID, as a string |

## Deploying a change

1. Edit `telegram-trigger.js` here and commit, so the repo stays the source of truth
2. Cloudflare dashboard → the worker → **Edit code**
3. Replace the whole file, **Save and deploy**
4. Send `Status` in Telegram and confirm the branch shown in the reply
5. Send `Update` and confirm the message format matches the branch you expect

Step 4 is the check that catches a wrong ref before a wrong report does.
