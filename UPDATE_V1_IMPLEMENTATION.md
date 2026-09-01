# UPDATE v1 — Surgical Implementation Record

Status: implemented on `main` as a transitional/pre-C15 boundary correction.

## Scope

UPDATE is the fast, user-triggered operational wing. ANALYZE is the scheduled historical/analytical wing.

```text
User /update
    ↓
Collect current market
    ↓
Validate
    ↓
Persist canonical observations
    ↓
Calculate current SP-A state
    ↓
Resolve RUN / DAY baselines
    ↓
Persist current market snapshot
    ↓
Telegram UPDATE v1
```

Scheduled ANALYZE continues to own news ingestion and analysis-snapshot construction.

## Baselines

### RUN

Latest canonical `market_snapshots` record available before the current UPDATE snapshot is persisted.

### DAY

Transitional definition: earliest canonical `market_snapshots` record of the current calendar day.

When the Analyze wing becomes the controlled daily collection source, DAY can be switched to the first controlled Analyze snapshot without changing the Telegram contract.

## UPDATE data model

The Telegram message exposes:

- XAU/USD
- USD/IRR
- Fair Price
- Platform Average
- Bubble (signed premium/discount state)
- RUN and DAY changes
- Local price direction
- Price acceleration
- Bubble movement
- Premium candle classification
- Market structure
- Platform-level RUN and DAY changes
- Current SP-A decision state

Price pace and bubble pace remain `N/A` until sufficient empirical history exists to calibrate defensible thresholds.

## Important analytical correction

Local-price acceleration is calculated from the arithmetic platform average of canonical market snapshots. It is intentionally not calculated from the raw `REP_IRAN_GOLD` observation stream because that stream contains multiple platform observations and Goldika BUY/SELL observations. Treating those records as consecutive prices can manufacture false acceleration from source ordering or bid/ask spread.

## Threshold status

| Primitive | Current rule | Calibration |
|---|---|---|
| Bubble movement | 0.05 percentage-point dead-band | Existing project convention; not empirically calibrated |
| Price direction | 0.01% relative dead-band | Placeholder; not calibrated |
| Price acceleration | 0.01% relative dead-band | Placeholder; not calibrated |
| Price pace | `N/A` | Deferred |
| Bubble pace | `N/A` | Deferred |

## Architecture boundary

UPDATE must not execute:

- news ingestion
- full C.3–C.10 analytical pipeline
- analysis snapshot construction
- forecast generation
- outcome evaluation

Those operations remain owned by the scheduled ANALYZE path.

## Neon

No schema migration is required for UPDATE v1.

## Safety / reversibility

The change is a surgical presentation/execution-boundary correction on `main`. Existing legacy Telegram formatting remains available as a fallback. SP-A decision logic and the database schema were not modified.

## Validation status

Repository-level inspection identified and corrected the initial KIMI integration defects before validation:

1. `src/main.py` had been concatenated with a duplicate/legacy file body and was syntactically invalid.
2. The proposed main path referenced a non-existent `save_price_observations()` repository function and wrong collector module names.
3. The initial acceleration implementation used raw mixed-platform observations, which could interpret source ordering or Goldika BUY/SELL spread as temporal acceleration.
4. The UPDATE formatter was isolated into `src/alerts/telegram_update_v1.py` so the legacy Telegram module remains intact.
5. The existing alert, daily recap, persistence, and scheduled Analyze paths were restored rather than silently removed.

The full KPI suite still requires execution in the project runtime after this surgical repair. No claim of KPI pass is made here until that execution is observed.
