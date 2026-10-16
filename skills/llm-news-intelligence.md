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

## Where the news comes from

- **RSS feeds**, read by GitHub's runner (`config.news.sources`).
- **Telegram channels**, read from GitHub's side, because t.me is blocked from Iran
  (`collector/news/telegram_channels.py`; research so far).
- **Iranian sites that refuse the runner** (cbi.ir, Tasnim, Donya-e-Eqtesad) are read by the owner's
  phone (`iran_node/`), as TSETMC is.

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
