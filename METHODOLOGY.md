# PE Multiples Monitor — Methodology

How the agent decides what counts as a "meaningful disconnect," how it presents
it, and how it runs. This is the plain-English companion to the code in
[`pe_monitor/`](pe_monitor/).

---

## 1. Data source

Everything comes from the static, CORS-open dashboard API at
`https://vhung-1.github.io/PEhistory/`:

| File | What we use it for |
|---|---|
| `api.json` | Cheap freshness probe — just the top-level `asof` date. |
| `data.json` | The NTM **forward-P/E panel**: `pe[TICKER][i]` on `dates[i]`, plus `sectors` and `sector_of`. 85 names, ~1,565 daily points back to 2020. |
| `q_pairs.json` | Per-pair **quarterly mean-reversion records** (95 within-sector pairs): current deviation, monthly deviation history, and quality stats (IC, hit rate). |

We never recompute pairs ourselves — the dashboard already curates a high-quality
within-sector pair list, and we consume it.

---

## 2. Signal 1 — Single-name vs its own P/E history

For each of the 85 tickers we ask: *is the stock's current forward P/E unusually
far from where it normally trades?*

1. Take the ticker's forward-P/E series, drop nulls (pre-listing gaps).
2. Require at least `SINGLE_MIN_HISTORY` (default **252**, ~1y) observations.
3. Define a trailing window of `SINGLE_LOOKBACK_DAYS` (default **756**, ~3y);
   fall back to full history for younger listings.
4. Over that window compute:
   - **mean** and **standard deviation** (σ);
   - **z-score** = `(current P/E − mean) / σ`;
   - **% deviation** = `(current / mean − 1) × 100`;
   - **percentile** of the current value within the window.
5. **Flag** the name when **both**:
   - `|z| ≥ SINGLE_Z` (default **2.0**), **and**
   - `|% deviation| ≥ SINGLE_MIN_PCT` (default **10%**).

The `|z|` test finds statistically unusual dislocations; the `%` floor stops a
low-volatility name from tripping on a trivially small absolute move. Direction:
`z > 0` → **RICH** (expensive vs history), `z < 0` → **CHEAP**.

Names are ranked by `|z|`.

---

## 3. Signal 2 — Pair-trade vs the pair's average

For relative-value pairs (e.g. *RJF vs LPLA*) we ask: *is the pair's P/E ratio
trading well away from its own long-run average — and is this a pair that
historically reverts?*

The dashboard precomputes, per pair, `devnow` = `(current ratio A/B ÷ long-run
average ratio) − 1`, in %, plus `ser` (its monthly deviation history) and quality
stats. We:

1. Compute the **z-score** of the current deviation against the pair's own
   history: `z = (devnow − mean(ser)) / σ(ser)`.
2. **Gate on reliability** — only consider pairs that have historically
   mean-reverted:
   - information coefficient `IC ≥ PAIR_IC_MIN` (default **0.30**),
   - quarterly hit rate `hit ≥ PAIR_HIT_MIN` (default **60%**),
   - at least `PAIR_MIN_NQ` (default **6**) quarters of history.
3. **Flag** a qualifying pair when it is stretched: `|z| ≥ PAIR_Z` (default
   **2.0**) **or** `|devnow| ≥ PAIR_DEV_PCT` (default **15%**).

**Suggested trade** (mean-reversion): the relatively cheap leg is the long.
`devnow < 0` (ratio A/B below average → A cheap vs B) → **Long A / Short B**;
`devnow > 0` → **Long B / Short A**.

Pairs are ranked by `|z| × IC` (how stretched × how reliable).

> **Why the reliability gate matters.** Close substitutes (alt managers, exchange
> operators) oscillate around a stable relative multiple and clear the gate;
> structurally diverging pairs (e.g. a mega-cap network vs an unprofitable
> fintech) never revert and are correctly excluded. This is deliberately a higher
> bar than the single-name signal.

---

## 4. How the report is organised

The email **walks through every sub-sector** in the dashboard's own order —
Exchanges, Info Services, Payments & Fintech, M&A Boutiques, Alternatives,
Traditional AM, Wealth & Brokers — so nothing is silently filtered out of view.

For each sub-sector:
- **Single-name** dislocations: a chart of the most-stretched name
  (P/E history with the average and ±1σ/±2σ bands, current point marked) + a
  full table (P/E now, average, % dev, z-score, percentile).
- **Pair-trade** dislocations: a chart of the top pair (deviation-from-average
  history with bands) + a table (deviation, z-score, IC, hit, suggested trade).
- Sub-sectors with nothing beyond thresholds are shown explicitly as
  *"no dislocations today."*

Charts are rendered with matplotlib (`CHARTS_SINGLE_PER_SECTOR` /
`CHARTS_PAIR_PER_SECTOR`, default 1 each).

---

## 5. Delivery

- Email is sent via the **Brevo** transactional API (`/v3/smtp/email`).
- Brevo has no inline-image support and Gmail/Workspace strips `data:` image
  URIs, so charts are committed to the repo and referenced by absolute
  `raw.githubusercontent.com` URL (which Gmail's image proxy fetches reliably).
  `CHART_MODE=datauri` embeds them instead for local preview.

---

## 6. Scheduling & the new-data gate

The GitHub Action runs **every morning (11:26 UTC)** but only does work when the
core data has actually been refreshed:

1. **check** — read the dashboard's `asof`; compare to the last processed value
   in `state/last_asof.txt`.
2. If unchanged → exit quietly (no email).
3. If new → **build** (compute signals, render charts, update the state file) →
   **commit** charts + state (so chart URLs go live) → **send**.

So you get exactly one email per data refresh — no duplicates, no empty days.
`Run workflow → force: true` sends regardless. When no name/pair breaches
thresholds on a genuine new-data day, `SEND_WHEN_EMPTY` (default true) still
sends a short "all-clear" so you know it ran.

---

## 7. Tunable parameters

All are environment variables (see [`.env.example`](.env.example)); the CI values
live in the workflow `env:` block.

| Variable | Default | Meaning |
|---|---|---|
| `SINGLE_LOOKBACK_DAYS` | 756 | Trailing window for single-name mean/σ |
| `SINGLE_MIN_HISTORY` | 252 | Min observations to consider a name |
| `SINGLE_Z` | 2.0 | Single-name z-score threshold |
| `SINGLE_MIN_PCT` | 10 | Single-name % deviation floor |
| `PAIR_Z` | 2.0 | Pair z-score threshold |
| `PAIR_DEV_PCT` | 15 | Pair absolute-deviation threshold |
| `PAIR_IC_MIN` | 0.30 | Min pair information coefficient (reliability) |
| `PAIR_HIT_MIN` | 60 | Min pair quarterly hit rate % |
| `PAIR_MIN_NQ` | 6 | Min quarters of pair history |
| `CHARTS_SINGLE_PER_SECTOR` | 1 | Single-name charts per sub-sector |
| `CHARTS_PAIR_PER_SECTOR` | 1 | Pair charts per sub-sector |
| `SEND_WHEN_EMPTY` | true | Email even with zero alerts on a new-data day |

---

*Not investment advice — a monitoring tool over public dashboard data.*
