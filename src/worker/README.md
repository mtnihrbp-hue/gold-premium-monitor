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
body: JSON.stringify({ ref: "SP-C" }),
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

Step 4 is the check that catches a wrong ref before a wrong report does.


## Pending improvements, not yet deployed

Neither is urgent and neither justifies a redeploy on its own. Apply them the next
time the worker is edited for another reason. They are recorded here rather than
applied to the file above, because this file mirrors what is **actually running** and
must not be allowed to describe something else.

**1. `Status` reports the wrong workflow.** It queries the unscoped runs endpoint,
which returns the newest run of *any* workflow in the repository, so it can report a
KPI suite run instead of the monitor. Scope it:

```js
const url = `https://api.github.com/repos/${env.GITHUB_REPO}` +
  `/actions/workflows/gold-monitor.yml/runs?per_page=1&branch=SP-C`;
```

Adding `run.name` to the reply also surfaces which wing ran, since the workflow's
`run-name` resolves to UPDATE or ANALYZE.

**2. The ref appears in two places** — the dispatch body and, once the fix above
lands, the status query. Lifting it to a single `const TARGET_REF` at the top of the
file makes the value that decides which version of the system answers a user visible
rather than buried in a request body, and makes the merge-time change one edit.
