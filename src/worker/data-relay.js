// ============================================
// Data relay - Cloudflare Worker (SP-D, 2026-10-04)
// ============================================
//
// GitHub's runner cannot reach two Iranian sources the PAPER analyst needs: Daric's order
// book (403 to foreign addresses) and TSETMC, the Tehran exchange's data (connection
// refused). Iranian geo-blocking may treat Cloudflare's network more kindly than
// GitHub's (owner, 2026-10-04); this worker fetches those sources from Cloudflare and
// hands them to the runner. If it is blocked too, the route is a relay inside Iran.
//
// Read-only GETs to an allowlist, guarded by a shared token. Nothing is stored.
// SEPARATE from telegram-trigger.js: a new worker, deployed on its own.
//
// Env vars (Cloudflare Dashboard -> this worker -> Settings -> Variables):
//   RELAY_TOKEN = a long random string; the same value goes into the GitHub secret
//                 RELAY_TOKEN, and the worker's URL into the GitHub secret RELAY_URL.
//
// Use:  GET https://<worker>/?url=<encoded target>      header X-Relay-Token: <token>
//       GET https://<worker>/probe                      header X-Relay-Token: <token>
//         -> the status of every allowed source from Cloudflare's side, for testing.

const ALLOWED = [
  /^https:\/\/apisc\.daric\.gold\/loan\/api\/v1\/User\/Collateral\/GetGoldlPrice$/,
  /^https:\/\/cdn\.tsetmc\.com\/api\/ClientType\/GetClientTypeHistory\/\d+$/,
  /^https:\/\/cdn\.tsetmc\.com\/api\/ClosingPrice\/GetClosingPriceDailyList\/\d+\/\d+$/,
  /^https:\/\/cdn\.tsetmc\.com\/api\/Instrument\/GetInstrumentSearch\/[^/?#]+$/,
];

const PROBES = [
  "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice",
  "https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/34144395039913458/0",
  "https://cdn.tsetmc.com/api/ClientType/GetClientTypeHistory/34144395039913458",
];

async function relay(target) {
  const started = Date.now();
  const upstream = await fetch(target, {
    headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/json" },
    cf: { cacheTtl: 0, cacheEverything: false },
  });
  return { upstream, ms: Date.now() - started };
}

export default {
  async fetch(request, env) {
    if (!env.RELAY_TOKEN || request.headers.get("X-Relay-Token") !== env.RELAY_TOKEN) {
      return new Response("Unauthorized", { status: 403 });
    }
    const url = new URL(request.url);

    if (url.pathname === "/probe") {
      const results = [];
      for (const target of PROBES) {
        try {
          const { upstream, ms } = await relay(target);
          const text = await upstream.text();
          results.push({ target, status: upstream.status, ms, bytes: text.length, head: text.slice(0, 120) });
        } catch (e) {
          results.push({ target, error: String(e) });
        }
      }
      return Response.json({ colo: request.cf && request.cf.colo, results });
    }

    const target = url.searchParams.get("url");
    if (!target || !ALLOWED.some((pattern) => pattern.test(target))) {
      return new Response("Target not allowed", { status: 400 });
    }
    try {
      const { upstream } = await relay(target);
      return new Response(await upstream.text(), {
        status: upstream.status,
        headers: {
          "Content-Type": upstream.headers.get("Content-Type") || "application/json",
          "X-Relay-Upstream-Status": String(upstream.status),
        },
      });
    } catch (e) {
      return new Response(`Relay fetch failed: ${e}`, { status: 502 });
    }
  },
};
