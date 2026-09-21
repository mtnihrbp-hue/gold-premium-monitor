// ============================================
// Gold Monitor Telegram Bot - Cloudflare Worker
// ============================================
//
// This file mirrors what is deployed on Cloudflare. It is not executed from this
// repository and nothing imports it; it is here so the deployed behaviour is
// reviewable and recoverable. Edit here first, then paste into the Cloudflare
// dashboard, so the two never drift.
//
// Env vars (Cloudflare Dashboard):
//   GITHUB_TOKEN       = Classic PAT with 'repo' scope
//   GITHUB_REPO        = "mtnihrbp-hue/gold-premium-monitor"  (full path!)
//   TELEGRAM_BOT_TOKEN = from @BotFather
//   TELEGRAM_CHAT_ID   = your chat ID

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Gold Monitor Bot is running", { status: 200 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("Bad JSON", { status: 400 });
    }

    const messageText = update.message?.text?.trim();
    const chatId = update.message?.chat?.id?.toString();

    if (!chatId || chatId !== env.TELEGRAM_CHAT_ID) {
      console.log(`Rejected chat: ${chatId}`);
      return new Response("Unauthorized", { status: 403 });
    }

    const command = messageText?.toLowerCase().replace(/^\//, "");

    // ─── /start or help ───
    if (!command || command === "start" || command === "help") {
      await sendTelegram(env, chatId,
        "🤖 <b>Gold Monitor Bot</b>\n\n" +
        "Commands:\n" +
        "• <b>Update</b> — Fresh market report (~1–2 min)\n" +
        "• <b>Analyze</b> — What the record shows (~1 min)\n" +
        "• <b>Status</b>  — Check latest workflow run\n\n" +
        "The bot will also send a heartbeat while collecting data."
      );
      return new Response("OK");
    }

    // ─── Update ───
    if (command === "update") {
      const ghRes = await triggerGitHub(env);

      if (!ghRes.ok) {
        let errBody = "";
        try { errBody = await ghRes.text(); } catch {}

        const errorMsg = `❌ <b>GitHub Error ${ghRes.status}</b>\n\n` +
          `${errBody.slice(0, 400)}\n\n` +
          `Check:\n` +
          `1. Token is <b>Classic</b> (not Fine-Grained)\n` +
          `2. Token has <b>repo</b> scope\n` +
          `3. Token not expired`;

        await sendTelegram(env, chatId, errorMsg);
        console.error(`GitHub ${ghRes.status}: ${errBody}`);
        return new Response("GitHub error", { status: 500 });
      }

      await sendTelegram(env, chatId, "⏳ <b>Update triggered</b>\nReport arriving in ~1–2 minutes...");
      return new Response("OK");
    }

    // ─── Analyze ───
    // Sends inputs.mode = "report", which is the read-only wing: it answers from
    // persisted state and collects nothing. skills/telegram-product.md requires that
    // a user request must not silently become an Analysis Wing execution.
    if (command === "analyze" || command === "analysis") {
      const ghRes = await triggerGitHub(env, "report");

      if (!ghRes.ok) {
        let errBody = "";
        try { errBody = await ghRes.text(); } catch {}
        await sendTelegram(env, chatId,
          `❌ <b>GitHub Error ${ghRes.status}</b>

${errBody.slice(0, 400)}`);
        console.error(`GitHub ${ghRes.status}: ${errBody}`);
        return new Response("GitHub error", { status: 500 });
      }

      await sendTelegram(env, chatId, "⏳ <b>Analyze triggered</b>\nReport arriving shortly...");
      return new Response("OK");
    }

    // ─── Status ───
    if (command === "status") {
      const statusMsg = await getWorkflowStatus(env);
      await sendTelegram(env, chatId, statusMsg);
      return new Response("OK");
    }

    // ─── Unknown ───
    await sendTelegram(env, chatId,
      "Unknown command. Send <b>Update</b>, <b>Analyze</b> or <b>Status</b>.");
    return new Response("OK");
  },
};

// Trigger GitHub Actions
//
// ref decides which branch's workflow file AND application code answer the user.
// It must match the ref cron-job.org sends, and both return to "main" when SP-C
// merges -- see the merge checklist in SP_C_HANDOFF.md.
async function triggerGitHub(env, mode) {
  // NOTE: GITHUB_REPO must be FULL path: "owner/repo-name"
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/gold-monitor.yml/dispatches`;

  // mode is omitted for /Update: the workflow declares a default of "update", which
  // GitHub applies, so SCHEDULED_RUN stays false and it takes the Live Wing path.
  // "report" is the read-only wing. Only cron-job.org sends "analyze", which is the
  // one that writes history.
  return fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "GoldMonitorBot/1.0",
    },
    body: JSON.stringify(
      mode ? { ref: "SP-C", inputs: { mode } } : { ref: "SP-C" }
    ),
  });
}

// Check latest workflow run
async function getWorkflowStatus(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/runs?per_page=1`;

  try {
    const res = await fetch(url, {
      headers: {
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "GoldMonitorBot/1.0",
      },
    });

    if (!res.ok) {
      return `❌ Failed to fetch status (HTTP ${res.status})`;
    }

    const data = await res.json();
    if (!data.workflow_runs || data.workflow_runs.length === 0) {
      return "ℹ️ No workflow runs found.";
    }

    const run = data.workflow_runs[0];
    const status = run.status;
    const conclusion = run.conclusion;
    const started = new Date(run.run_started_at).toLocaleString("en-GB", {
      timeZone: "Asia/Tehran",
      hour: "2-digit",
      minute: "2-digit",
      day: "numeric",
      month: "short",
    });

    let emoji = "⏳";
    let stateText = status;
    if (status === "completed") {
      emoji = conclusion === "success" ? "✅" : "❌";
      stateText = conclusion;
    }

    // run.name carries the workflow's run-name, which resolves to UPDATE or ANALYZE.
    return `${emoji} <b>Latest Run</b>\n` +
           `Wing: ${run.name || "n/a"}\n` +
           `Status: ${stateText}\n` +
           `Started: ${started} (Tehran)\n` +
           `<a href="${run.html_url}">View on GitHub →</a>`;
  } catch (e) {
    return `❌ Error: ${e.message}`;
  }
}

// Send Telegram message
async function sendTelegram(env, chatId, text) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;

  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    }),
  });
}
