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
//   GITHUB_TOKEN            = a fine-grained token: this repository only, Actions read and write, with an
//                             expiry (the external audit's A2, SP_D_HANDOFF.md section 52)
//   GITHUB_REPO             = "mtnihrbp-hue/gold-premium-monitor"  (full path!)
//   TELEGRAM_BOT_TOKEN      = from @BotFather
//   TELEGRAM_CHAT_ID        = your chat ID
//   TELEGRAM_WEBHOOK_SECRET = the secret_token the webhook was registered with (A1). When set, a request
//                             without Telegram's matching header is refused.
// Binding (optional): DEBOUNCE, a KV namespace. With it, each command is dispatched at most once a minute.

// The branch whose workflow file AND application code answer the user. It must match
// the ref cron-job.org sends. Both were repointed from "SP-C" to "main" on 2026-09-28,
// after the merge (SP_C_HANDOFF.md section 35). One definition, used by the dispatch
// and by Status.
const TARGET_REF = "main";

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Gold Monitor Bot is running", { status: 200 });
    }

    // Only Telegram knows the secret it was registered with, and sends it in this header. The chat id inside
    // the body is a number, not a secret: anyone who learned this address could otherwise dispatch production
    // runs (the external audit's A1).
    if (env.TELEGRAM_WEBHOOK_SECRET &&
        !sameSecret(request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "", env.TELEGRAM_WEBHOOK_SECRET)) {
      console.log("Rejected: no matching secret token");
      return new Response("Unauthorized", { status: 403 });
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
        "• <b>Direction</b> — Where the 18K trend stands (~1 min)\n" +
        "• <b>Status</b>  — Check latest workflow run\n\n" +
        "The bot will also send a heartbeat while collecting data."
      );
      return new Response("OK");
    }

    // One dispatch per command a minute: a repeated tap, or a burst, runs once.
    if (["update", "analyze", "analysis", "direction"].includes(command) && await debounced(env, command)) {
      await sendTelegram(env, chatId, "⏳ Already on its way: one per minute.");
      return new Response("OK");
    }

    // ─── Update ───
    if (command === "update") {
      const ghRes = await triggerGitHub(env);

      if (!ghRes.ok) {
        let errBody = "";
        try { errBody = await ghRes.text(); } catch {}

        const errorMsg = `❌ <b>GitHub Error ${ghRes.status}</b>\n\n` +
          `${escapeHtml(errBody.slice(0, 400))}\n\n` +
          `Check:\n` +
          `1. The token is for this repository, with Actions read and write\n` +
          `2. The token has not expired`;

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

${escapeHtml(errBody.slice(0, 400))}`);
        console.error(`GitHub ${ghRes.status}: ${errBody}`);
        return new Response("GitHub error", { status: 500 });
      }

      await sendTelegram(env, chatId, "⏳ <b>Analyze triggered</b>\nReport arriving shortly...");
      return new Response("OK");
    }

    // ─── Direction ───
    // inputs.mode = "direction" is read-only like "report": it renders the panel the
    // scheduled runs stored at 06:00 and 13:00 Tehran, and computes nothing.
    if (command === "direction") {
      const ghRes = await triggerGitHub(env, "direction");

      if (!ghRes.ok) {
        let errBody = "";
        try { errBody = await ghRes.text(); } catch {}
        await sendTelegram(env, chatId,
          `❌ <b>GitHub Error ${ghRes.status}</b>

${escapeHtml(errBody.slice(0, 400))}`);
        console.error(`GitHub ${ghRes.status}: ${errBody}`);
        return new Response("GitHub error", { status: 500 });
      }

      await sendTelegram(env, chatId, "⏳ <b>Direction triggered</b>\nPanel arriving shortly...");
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
      "Unknown command. Send <b>Update</b>, <b>Analyze</b>, <b>Direction</b> or <b>Status</b>.");
    return new Response("OK");
  },
};

// Trigger GitHub Actions on TARGET_REF.
async function triggerGitHub(env, mode) {
  // NOTE: GITHUB_REPO must be FULL path: "owner/repo-name"
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/gold-monitor.yml/dispatches`;

  // mode is omitted for /Update: the workflow declares a default of "update", which
  // GitHub applies, so SCHEDULED_RUN stays false and it takes the Live Wing path.
  // "report" and "direction" are read-only wings. Only cron-job.org sends "analyze",
  // which is the one that writes history.
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
      mode ? { ref: TARGET_REF, inputs: { mode } } : { ref: TARGET_REF }
    ),
  });
}

// Check latest workflow run
async function getWorkflowStatus(env) {
  // Scoped to the monitor's workflow on TARGET_REF: the unscoped endpoint returned the
  // newest run of any workflow, which could be a KPI suite run.
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}` +
    `/actions/workflows/gold-monitor.yml/runs?per_page=1&branch=${TARGET_REF}`;

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
    const service = await getServiceLine(env);
    return `${emoji} <b>Latest Run</b>\n` +
           `Wing: ${run.name || "n/a"}\n` +
           `Status: ${stateText}\n` +
           `Started: ${started} (Tehran)\n` +
           (service ? `${service}\n` : "") +
           `<a href="${run.html_url}">View on GitHub →</a>`;
  } catch (e) {
    return `❌ Error: ${e.message}`;
  }
}

// The service line the last scheduled run left (SP_D_HANDOFF.md section 37.15). A green run said
// nothing about the database: every run of the October outage finished green. Each scheduled run
// writes "::notice title=service::Service: ..." (src/main.py _service_watch), which GitHub keeps as an
// annotation of its job. "" when it cannot be read, so Status still answers.
async function getServiceLine(env) {
  const headers = {
    "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "GoldMonitorBot/1.0",
  };
  try {
    const runs = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}` +
      `/actions/workflows/gold-monitor.yml/runs?per_page=20&branch=${TARGET_REF}&status=completed`, { headers });
    if (!runs.ok) return "";
    const run = ((await runs.json()).workflow_runs || []).find(r => r.name === "ANALYZE");
    if (!run) return "";
    const jobs = await fetch(run.jobs_url, { headers });
    if (!jobs.ok) return "";
    const job = ((await jobs.json()).jobs || [])[0];
    if (!job) return "";
    const annotations = `https://api.github.com/repos/${env.GITHUB_REPO}/check-runs/${job.id}/annotations`;
    let notes = await fetch(annotations, { headers });
    if (notes.status === 403 || notes.status === 404) {
      // a fine-grained token may not reach check runs; the repository is public, so read without it
      const { Authorization, ...open } = headers;
      notes = await fetch(annotations, { headers: open });
    }
    if (!notes.ok) return "";
    const line = ((await notes.json()) || []).find(a => a.title === "service");
    if (!line) return "";
    const at = new Date(run.run_started_at).toLocaleString("en-GB", {
      timeZone: "Asia/Tehran", hour: "2-digit", minute: "2-digit" });
    return `${line.message} (the ${at} run)`;
  } catch (e) {
    return "";
  }
}

// The secret compared in constant time (the external audit's A1).
function sameSecret(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// True when the same command was dispatched in the last minute. Needs the DEBOUNCE KV binding; without it,
// nothing is held back. (Cloudflare's cache API does nothing on workers.dev addresses, so KV is used.)
async function debounced(env, command) {
  if (!env.DEBOUNCE) return false;
  const key = `cmd:${command === "analysis" ? "analyze" : command}`;
  try {
    if (await env.DEBOUNCE.get(key)) return true;
    await env.DEBOUNCE.put(key, "1", { expirationTtl: 60 });
  } catch (e) {
    console.log(`debounce unavailable: ${e}`);
  }
  return false;
}

// GitHub's error text is not ours: escaped before Telegram parses it as HTML.
function escapeHtml(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
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
