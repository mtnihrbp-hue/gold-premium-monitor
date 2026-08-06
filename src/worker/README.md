# Cloudflare Worker: Telegram Trigger

This folder contains the backup source code for the Cloudflare Worker that handles on-demand Telegram bot commands.

## What It Does

1. Receives webhook POST requests from Telegram
2. Validates the chat ID (security)
3. Listens for the "Update" or "/update" command
4. Triggers the GitHub Actions workflow via `workflow_dispatch`
5. Sends a "Collecting market data..." confirmation back to Telegram

## Environment Variables

Set these in the Cloudflare Workers dashboard (Settings → Variables):

| Variable | Description | Example |
|---|---|---|
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope | `ghp_xxxxxxxxxxxx` |
| `TELEGRAM_BOT_TOKEN` | From @BotFather | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Your numeric chat ID | `123456789` |
| `REPO_OWNER` | GitHub username | `mtnihrbp-hue` |
| `REPO_NAME` | Repository name | `gold-premium-monitor` |

## Deployment

### Option 1: Cloudflare Dashboard (Simple)

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages
2. Select your existing worker (or create new)
3. Paste `telegram-trigger.js` into the code editor
4. Go to **Settings → Variables** and add the 5 environment variables above
5. Click **Deploy**

### Option 2: Wrangler CLI (Advanced)

```bash
npm install -g wrangler
wrangler login
# Edit wrangler.toml if needed
wrangler deploy src/worker/telegram-trigger.js


### Webhook Setup
After deploying, tell Telegram where to send updates:

curl -X POST \
  "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-worker.your-subdomain.workers.dev"}'

### | Problem                 | Cause                    | Fix                                        |
| ----------------------- | ------------------------ | ------------------------------------------ |
| "Unauthorized" in logs  | Wrong `TELEGRAM_CHAT_ID` | Check your actual chat ID via @userinfobot |
| "Trigger failed"        | Invalid `GITHUB_TOKEN`   | Regenerate PAT with `repo` scope           |
| No response in Telegram | Webhook not set          | Run the webhook setup curl command above   |
| Duplicate messages      | Telegram retries         | Worker always returns 200 OK quickly       |

