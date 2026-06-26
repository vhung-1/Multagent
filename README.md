# PE Multiples Monitor

A daily agent that reads the [diversified-financials forward-P/E dashboard
API](https://vhung-1.github.io/PEhistory/api.json), flags **meaningful
disconnects** in valuation multiples, and emails an easy-to-digest HTML summary
(with charts) via the **Brevo** transactional email API.

It watches for two kinds of dislocation:

1. **Single-name vs its own P/E history** — when a stock's current NTM forward
   P/E is stretched far from its trailing average (z-score + % deviation +
   percentile).
2. **Pair-trade vs the pair's average** — when a relative-value pair's P/E ratio
   (e.g. *RJF vs LPLA*) is trading well away from its long-run average, gated on
   the pair's *historical mean-reversion reliability* (information coefficient
   and quarterly hit rate). The email suggests the mean-reversion trade
   (long the relatively cheap leg / short the rich leg).

## What the email looks like

- Header + one-line summary (how many names / pairs breached thresholds).
- **Single-name** section: charts of the most-stretched names (P/E history with
  the average and ±1σ/±2σ bands) followed by a full table.
- **Pair-trade** section: charts of the most-dislocated reliable pairs
  (deviation-from-average history) followed by a table with the suggested trade.
- Methodology footer + link back to the live dashboard.

## How it works

```
api.json / data.json / q_pairs.json   (GitHub Pages, CORS-open static JSON)
        │
        ▼
  pe_monitor build   → fetch → compute signals → render charts (PNG) + email.html
        │
        ▼
  pe_monitor send    → POST the HTML to Brevo /v3/smtp/email
```

- **Single-name z-score** = `(current P/E − trailing-window mean) / σ`, over a
  configurable lookback (default ~3y, falls back to full history for young
  listings). Flagged when `|z| ≥ SINGLE_Z` **and** `|% dev| ≥ SINGLE_MIN_PCT`.
- **Pair deviation** uses the dashboard's `devnow` = `current ratio (A/B) ÷
  long-run-average ratio − 1` (in %), z-scored against the pair's own monthly
  deviation history (`ser`). Flagged when the pair is *reliable*
  (`ic ≥ PAIR_IC_MIN`, `hit ≥ PAIR_HIT_MIN`, `nq ≥ PAIR_MIN_NQ`) **and**
  stretched (`|z| ≥ PAIR_Z` **or** `|devnow| ≥ PAIR_DEV_PCT`).

All thresholds are environment variables — see [`.env.example`](.env.example).

## Charts in email: why hosted URLs

Brevo's transactional API does **not** support inline (CID) images, and
Gmail/Workspace strips `data:` image URIs. So in production the agent renders
chart PNGs, commits them under `charts/<date>/`, and references them by absolute
`raw.githubusercontent.com` URL — which Gmail's image proxy fetches fine. Set
`CHART_MODE=datauri` for local previews (self-contained, opens in any browser /
Apple Mail).

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env            # fill in BREVO_API_KEY etc.
set -a; source .env; set +a

python -m pe_monitor build      # writes out/email.html + charts/<date>/*.png
open out/email.html             # preview (use CHART_MODE=datauri so charts embed)
python -m pe_monitor run        # build + send via Brevo
```

`build` / `send` are split so CI can publish the charts between them; `run` does
both in one process.

## Daily automation (GitHub Actions)

The workflow [`.github/workflows/daily-pe-monitor.yml`](.github/workflows/daily-pe-monitor.yml)
runs every weekday at 12:30 UTC: it builds the report, commits the day's charts
(so their URLs go live), then sends the email.

One-time setup in the repo:

1. **Settings → Secrets and variables → Actions → Secrets**
   - `BREVO_API_KEY` — your Brevo API key (Brevo → SMTP & API → API Keys).
2. **… → Variables**
   - `MAIL_TO` = `vhung@attelascap.com` (comma-separate for multiple)
   - `MAIL_SENDER_EMAIL` = a **verified sender/domain** in Brevo
   - `MAIL_SENDER_NAME` = `PE Multiples Monitor`
3. Verify the sender email/domain in Brevo (**Senders, Domains & Dedicated IPs**),
   otherwise sends are rejected.
4. Merge to the default branch — scheduled runs always execute on the default
   branch, which is also the branch the chart URLs point at.

Tune thresholds by editing the `env:` block in the workflow (or set them as repo
variables). Trigger a manual test run with **Actions → Daily PE Multiples
Monitor → Run workflow**.

## Layout

```
pe_monitor/
  config.py     env-driven configuration + thresholds
  fetch.py      load data.json / q_pairs.json
  analyze.py    single-name & pair-trade signal generation
  charts.py     matplotlib PNG charts
  render.py     HTML email template
  brevo.py      Brevo transactional email client
  __main__.py   CLI: build / send / run
```

*Not investment advice — a monitoring tool over public dashboard data.*
