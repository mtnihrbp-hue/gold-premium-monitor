# Data and Neon Skill

## Purpose

Preserve the project's historical memory and data-quality discipline.

## Database

Neon PostgreSQL is the project's production historical store.

Do not introduce SQLite or Supabase as an intermediate solution unless explicitly approved.

## Data layers

Keep these concepts separate:

```text
market observations
≠
interpreted market state
≠
prediction outcome
```

Raw observations should remain queryable.

Interpreted states should remain queryable.

Future predictions/outcomes should be linked to the state that generated them.

## Historical memory

The purpose of Neon is not just logging.

Historical data must eventually support questions such as:

- What happened after similar premium conditions?
- What happened when USD was near resistance?
- How often did BUY candidates become successful outcomes?
- Which news events historically mattered?

Design new schemas so future analysis remains possible.

## Data quality

Unknown is better than fabricated.

Use explicit states such as:

- `UNKNOWN`
- `INSUFFICIENT DATA`
- `DEGRADED`

Do not turn missing values into zero unless zero is semantically valid.

## External failures

Neon failure must not crash the core market monitor.

Preserve existing fallback behavior.

Collectors may fail independently.

Optional intelligence may become `UNKNOWN` while quantitative monitoring continues.

## Numeric integrity

Do not allow an LLM to invent:

- USD/IRR
- XAU/USD
- fair price
- premium
- platform prices
- support/resistance
- historical returns

These belong to deterministic code and stored data.

## Future historical analysis

Always expose sample size before interpreting historical evidence.

Never call a three-observation pattern a reliable probability.

Prefer:

```text
sample size
→ observed outcome
→ uncertainty
```

over opaque confidence numbers.
