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
3. Handles `Update`, `Analyze`, `Direction`, `Status`, `start` / `help`
4. `Update`, `Analyze` (mode `report`) and `Direction` (mode `direction`) trigger
   `gold-monitor.yml` via `workflow_dispatch` on `TARGET_REF`
5. `Status` reports the newest run of that workflow on that branch

## The branch ref

```js
const TARGET_REF = "main";
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
| `GITHUB_TOKEN` | A fine-grained token: this repository only, Actions read and write, with an expiry. Since 2026-10-18; the classic `repo` token is revoked (the external audit's A2, `SP_D_HANDOFF.md` 52). Fine-grained tokens do work for dispatches. |
| `GITHUB_REPO` | **Full** path, `owner/repo` — e.g. `mtnihrbp-hue/gold-premium-monitor` |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | Numeric chat ID, as a string |
| `TELEGRAM_WEBHOOK_SECRET` | The `secret_token` the webhook is registered with (A1). When set, a request without Telegram's matching `X-Telegram-Bot-Api-Secret-Token` header is refused. Letters, digits, `_` and `-`, up to 256. |

Binding (Settings → Bindings), optional: a KV namespace named `DEBOUNCE`. With it, each command is
dispatched at most once a minute; without it, nothing is held back. Cloudflare's cache API cannot do this on a
`workers.dev` address.

The webhook is registered with its secret once, in a browser:
`https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<the worker's address>&secret_token=<the secret>`.
Register it first, then set the variable and paste the worker: the old worker ignores the header, so nothing
is refused in between.

`tests/test_worker.py` runs the worker's behaviour in Node (`tests/worker_behaviour.mjs`).

## Validating before you deploy

`node --check file.js` **silently passes a file containing `export`** -- it cannot
parse it as CommonJS, falls back, and returns 0 without validating anything. This
worker uses `export default`, so every `node --check` run against it during SP-C.12
reported success while an unterminated string sat on line 94.

Check it as a module:

```
cp src/worker/telegram-trigger.js /tmp/w.mjs && node --check /tmp/w.mjs
```

The `.mjs` extension is what makes node parse it as an ES module and actually look.

## Deploying a change

1. Edit `telegram-trigger.js` here and commit, so the repo stays the source of truth
2. Cloudflare dashboard → the worker → **Edit code**
3. Replace the whole file, **Save and deploy**
4. Send `Status` in Telegram and confirm the branch shown in the reply
5. Send `Update` and confirm the message format matches the branch you expect
6. Send `Analyze` and confirm a report arrives. It reads persisted state and writes
   nothing, so it is safe to send repeatedly.
7. Send `Direction` and confirm the DIRECTION panel arrives. It renders the panel the
   scheduled runs stored (from 06:00 and 13:00 Tehran) and writes nothing.

Step 4 is the check that catches a wrong ref before a wrong report does.

## Applied 2026-10-03, with the Direction command

The two improvements that waited for the next edit: `Status` is scoped to
`gold-monitor.yml` on `TARGET_REF` (the unscoped endpoint could report a KPI suite run),
and the ref is one `const TARGET_REF` used by the dispatch and by `Status`.
