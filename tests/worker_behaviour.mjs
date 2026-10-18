// Behaviour test of src/worker/telegram-trigger.js with fake GitHub, Telegram and KV (no network): the
// webhook secret, the one-a-minute hold, escaped errors (the external audit's A1; SP_D_HANDOFF.md 52).
// Run by tests/test_worker.py: node tests/worker_behaviour.mjs <worker.js> <a copy to write as .mjs>
import { readFileSync, writeFileSync } from "node:fs";
import assert from "node:assert/strict";

const src = readFileSync(process.argv[2], "utf8");
const copy = process.argv[3];
writeFileSync(copy, src);
const worker = (await import("file:///" + copy.replace(/\\/g, "/"))).default;

const calls = [];
globalThis.fetch = async (url, init = {}) => {
  calls.push({ url: String(url), init });
  if (String(url).includes("/dispatches")) return new Response(null, { status: 204 });
  if (String(url).includes("api.telegram.org")) return new Response("{}", { status: 200 });
  return new Response("<b>boom</b> & more", { status: 500 });
};

const kv = new Map();
const env = {
  TELEGRAM_CHAT_ID: "42", TELEGRAM_BOT_TOKEN: "t", GITHUB_TOKEN: "g", GITHUB_REPO: "o/r",
  TELEGRAM_WEBHOOK_SECRET: "s3cret_value",
  DEBOUNCE: { get: async k => kv.get(k) || null, put: async (k, v) => kv.set(k, v) },
};
const update = text => JSON.stringify({ message: { text, chat: { id: 42 } } });
const req = (text, secret) => new Request("https://w.example/", {
  method: "POST", body: update(text),
  headers: secret === undefined ? {} : { "X-Telegram-Bot-Api-Secret-Token": secret },
});

// 1. no header, wrong header: refused before anything is dispatched
assert.equal((await worker.fetch(req("Update"), env)).status, 403);
assert.equal((await worker.fetch(req("Update", "s3cret_valuX"), env)).status, 403);
assert.equal(calls.length, 0, "nothing dispatched without the secret");

// 2. the right header: dispatched once; the same command within a minute is held
assert.equal((await worker.fetch(req("Update", "s3cret_value"), env)).status, 200);
assert.equal(calls.filter(c => c.url.includes("/dispatches")).length, 1);
await worker.fetch(req("Update", "s3cret_value"), env);
assert.equal(calls.filter(c => c.url.includes("/dispatches")).length, 1, "debounced");
const held = calls.filter(c => c.url.includes("api.telegram.org")).pop();
assert.match(JSON.parse(held.init.body).text, /one per minute/);

// 3. another command is not held by the first; analysis and analyze share one key
await worker.fetch(req("Direction", "s3cret_value"), env);
assert.equal(calls.filter(c => c.url.includes("/dispatches")).length, 2);

// 4. without the secret configured, the old behaviour (the switch-over order) and no KV: no debounce
const open = { ...env, TELEGRAM_WEBHOOK_SECRET: undefined, DEBOUNCE: undefined };
assert.equal((await worker.fetch(req("Update"), open)).status, 200);
assert.equal((await worker.fetch(req("Update"), open)).status, 200);
assert.equal(calls.filter(c => c.url.includes("/dispatches")).length, 4);

// 5. a GitHub error body is escaped before Telegram parses it as HTML
globalThis.fetch = async (url, init = {}) => {
  calls.push({ url: String(url), init });
  if (String(url).includes("/dispatches")) return new Response("<b>bad</b> & worse", { status: 422 });
  return new Response("{}", { status: 200 });
};
kv.clear();
await worker.fetch(req("Analyze", "s3cret_value"), env);
const err = JSON.parse(calls.filter(c => c.url.includes("api.telegram.org")).pop().init.body).text;
assert.ok(err.includes("&lt;b&gt;bad&lt;/b&gt; &amp; worse"), err);

// 6. a wrong chat id is still refused
const other = new Request("https://w.example/", { method: "POST",
  body: JSON.stringify({ message: { text: "Update", chat: { id: 7 } } }),
  headers: { "X-Telegram-Bot-Api-Secret-Token": "s3cret_value" } });
assert.equal((await worker.fetch(other, env)).status, 403);
console.log("worker behaviour: all checks passed");
