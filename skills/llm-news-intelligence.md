# LLM and News Intelligence Skill

## Purpose

Define the safe role of LLMs when external intelligence is added.

## Core boundary

```text
Quant engine
= measures

LLM
= interprets external information

Decision engine
= decides
```

Do not allow an LLM to become the quantitative engine.

## News event extraction

A news item should be transformed into structured market context such as:

- event type
- topic
- factual summary
- impact
- confidence
- uncertainty
- expected USD/IRR direction
- expected Iranian-gold direction
- expected duration
- source
- publication time

Use controlled vocabularies where practical.

Allow `UNKNOWN` and `UNCERTAIN`.

## LLM output validation

Never trust raw LLM output.

Required pipeline:

```text
news
→ LLM
→ structured response
→ schema validation
→ enum validation
→ normalization
→ database
```

Malformed output must not become market truth.

## No fabrication

The LLM must not invent:

- prices
- rates
- fair value
- premium
- support/resistance
- historical outcomes
- economic statistics not present in the supplied evidence

## Decision boundary

News can support or contradict quantitative market state.

It should not independently create BUY/SELL decisions.

Example:

```text
Quant state: CHEAP + IMPROVING
News: high-impact geopolitical deterioration

Result:
NEWS CONTRADICTS / RAISES RISK
```

The deterministic decision layer remains explicit.

## Cost constraint

The project is free-tier only.

Groq's free tier caps the minute (about 8,000 tokens for the model used) and the day: about 108
labelled days per 5-hour run (`SP_D_HANDOFF.md` 35.9, 36.5). Pace requests under the cap, and plan
a backfill across days.

Minimize calls.

Deduplicate news.

Do not process the same article repeatedly without a reason.

Use mocked LLM responses in the normal automated test suite.

## Failure behavior

If the LLM is unavailable:

- market monitoring continues
- deterministic state continues
- news-derived fields become `UNKNOWN`
- the worker does not crash

## The one AI call in production: the LENS's headlines

Since 2026-10-31 on sp-de (owner: "1-approved. 2-go ahead"; `SP_D_HANDOFF.md` 86), `intelligence/news_lens.py`:
- **The input:** the last 24 hours of the four channels' headlines, filtered as the labelling filters them,
  never a price.
- **The task:** the model only picks (at most three toward a strike, three toward a deal) and translates.
- **The translation rules** (tested 2026-10-31, `SP_D_HANDOFF.md` 87): the meaning, not the words; who says it
  stays, an outlet transliterated rather than replaced; a condition stays a condition. The first prompt dropped
  "Axios" in 3 of 3 rounds and a threat's "if" in 2 of 3. Test a prompt change the same way: one headline list,
  three rounds each, beside the Persian. The model is not deterministic at temperature 0, so one run proves nothing.
- **The checks:** `validate` drops a pick it was not given, a headline on both sides, and a translation
  carrying a number its headline does not carry.
- **When it fails:** no key, a spent daily quota or an unreadable reply leave the news out, and the lens says so.
- **What it never does:** the read is not the model's. Neither is any number.
- **The cost:** one request a night, about 2,900 tokens of the shared 200,000.

## Where the news comes from

- **RSS feeds**, read by GitHub's runner (`config.news.sources`).
- **Telegram channels**, read from GitHub's side, because t.me is blocked from Iran
  (`collector/news/telegram_channels.py`; the LENS's headlines). A page of photos alone has no posts and is
  not the channel's end: page back from `page_messages`, every message, text or not (`SP_D_HANDOFF.md` 87).
- **The Iranian sites** (Tasnim, cbi.ir, Donya-e-Eqtesad, Tejarat News) are read by GitHub's runner too.
  Tasnim moved to `tasnimnews.ir`, and cbi.ir rejects some user agents and serves no charset. Before
  routing a source to the phone (`iran_node/`, as TSETMC is), probe it from the runner
  (`SP_D_HANDOFF.md` 37.13).

The keyword classifier gives the event type and impact, never a gold direction (UNKNOWN since
2026-09-21). Keywords cannot find events: in a year with a war, "military" matched 253 of 357 days.
Labelling a day needs the model.

## What has been measured

On 152 of 357 labelled days (`SP_D_HANDOFF.md` 36.2, 37.11), the rest running:
- the model's own call on the dollar showed no skill;
- the central bank's interventions met pressure and did not reverse it;
- escalation separated on 108 days and stopped separating on 152: a result from one window is not a
  result (lesson 22).

Only a label that separates on the whole record may reach a reader, with its counts.

## Historical learning

Persist the structured event and later compare its expected direction with the actual market reaction.

Do not claim that an LLM interpretation was correct merely because price moved afterward. Preserve the event context and evaluate it by defined horizons.
