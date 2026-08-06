/**
 * Cloudflare Worker: Telegram Bot Webhook → GitHub Actions Trigger
 *
 * Receives Telegram webhook updates, validates the chat, and triggers
 * the gold-monitor GitHub Actions workflow via workflow_dispatch.
 *
 * Environment Variables (set in Cloudflare Workers dashboard):
 *   GITHUB_TOKEN       - GitHub Personal Access Token with repo scope
 *   TELEGRAM_BOT_TOKEN - From @BotFather
 *   TELEGRAM_CHAT_ID   - Your Telegram chat ID (numeric string)
 *   REPO_OWNER         - GitHub username (e.g., "mtnihrbp-hue")
 *   REPO_NAME          - Repository name (e.g., "gold-premium-monitor")
 */

const GITHUB_API = "https://api.github.com";

addEventListener("fetch", (event) => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  // Only accept POST from Telegram
  if (request.method !== "POST") {
    return new Response("OK", { status: 200 });
  }

  let update;
  try {
    update = await request.json();
  } catch (e) {
    return new Response("Bad Request", { status: 400 });
  }

  const message = update.message || update.edited_message;
  if (!message || !message.text) {
    return new Response("No text", { status: 200 });
  }

  const chatId = String(message.chat.id);
  const text = message.text.trim();

  // Security: validate chat ID
  if (chatId !== TELEGRAM_CHAT_ID) {
    return new Response("Unauthorized", { status: 403 });
  }

  // Only respond to "Update" or "/update"
  const command = text.toLowerCase();
  if (command !== "update" && command !== "/update") {
    return new Response("Unknown command", { status: 200 });
  }

  // Trigger GitHub Actions workflow
  const triggerUrl = `${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/gold-monitor.yml/dispatches`;

  try {
    const githubResponse = await fetch(triggerUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${GITHUB_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "gold-premium-monitor-worker",
      },
      body: JSON.stringify({
        ref: "main",
      }),
    });

    if (!githubResponse.ok) {
      const errorText = await githubResponse.text();
      console.error(`GitHub API error: ${githubResponse.status} ${errorText}`);
      return new Response("Trigger failed", { status: 200 });
    }

    // Optionally notify user that the update is running
    await sendTelegramMessage(chatId, "⏳ Collecting market data...");

    return new Response("Triggered", { status: 200 });
  } catch (e) {
    console.error(`Worker error: ${e.message}`);
    return new Response("Error", { status: 200 });
  }
}

async function sendTelegramMessage(chatId, text) {
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: text,
        parse_mode: "HTML",
      }),
    });
  } catch (e) {
    console.error(`Telegram notify error: ${e.message}`);
  }
}
