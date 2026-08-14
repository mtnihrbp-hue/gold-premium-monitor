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

## Historical learning

Persist the structured event and later compare its expected direction with the actual market reaction.

Do not claim that an LLM interpretation was correct merely because price moved afterward. Preserve the event context and evaluate it by defined horizons.
