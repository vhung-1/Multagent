# How the Monitor Accesses the PE Multiples API

A reference for the data layer of the PE Multiples Monitor — where the data
lives, which endpoints are read, their shapes, and how the code in
[`pe_monitor/fetch.py`](pe_monitor/fetch.py) consumes them.

---

## 1. The API

The dashboard is a set of **static JSON files served by GitHub Pages** at:

```
https://vhung-1.github.io/PEhistory/
```

Key properties:
- **No authentication** — plain public HTTPS GETs.
- **CORS-open** — every endpoint returns `Access-Control-Allow-Origin: *`.
- **Snapshot-based** — the top-level `asof` field is the build date; data
  refreshes when the PEhistory `main` branch is rebuilt.

The base URL is configurable via the `PE_BASE_URL` environment variable
(default above), so the monitor can be pointed at a fork or a local mirror.

---

## 2. Endpoints the monitor reads

The monitor only needs three of the published endpoints:

| Endpoint | Size | Used for | Read by |
|---|---|---|---|
| `api.json` | ~5 KB | Freshness probe — just the `asof` date | `fetch_asof()` (the daily new-data gate) |
| `data.json` | ~780 KB | The forward-P/E panel (single-name signal) | `load_dashboard()` |
| `q_pairs.json` | ~280 KB | Pair mean-reversion records (pair signal) | `load_dashboard()` |

Other published endpoints (`daily_px.json`, `sw_data.json`, `btdata.json`,
`bt_results.json`, `Relative_PE_Dashboard.html`) are **not** consumed.

---

## 3. Endpoint shapes (the fields we use)

### `api.json`
```jsonc
{
  "asof": "2026-07-02",           // <- the only field the gate reads
  "dates": { "first": "...", "last": "...", "count": 1565 },
  "universe": { "count": 85, "tickers": [...], "sectors": {...} },
  "endpoints": [...],
  ...
}
```

### `data.json`
```jsonc
{
  "asof": "2026-07-02",
  "dates": ["2020-06-26", ...],          // index i aligns across all series
  "pe": { "RJF US": [11.54, 11.6, ...], ... },  // pe[TICKER][i] on dates[i]; null before listing
  "sectors": { "Exchanges": ["CME US", ...], ... },  // drives the sub-sector walk
  "sector_of": { "RJF US": "Wealth & Brokers", ... },
  "excluded": ["RELY LN", "SQ SW"]
}
```

### `q_pairs.json`
```jsonc
[
  {
    "a": "LPLA US", "b": "RJF US", "sec": "Wealth & Brokers",
    "nq": 14, "hit": 57, "ic": 0.44,      // reliability stats (gate)
    "devnow": -24.5,                       // current ratio deviation vs avg, %
    "ser": [ { "t": "2026-06", "d": -4.4 }, ... ],  // monthly deviation history (z-score basis)
    "q": [ ... ]                           // per-quarter records (not used by the monitor)
  },
  ...
]
```

---

## 4. How the code fetches it

All access goes through [`pe_monitor/fetch.py`](pe_monitor/fetch.py) using
`requests` with a 30-second timeout and `raise_for_status()` (any non-200 aborts
the run loudly rather than emailing stale/garbage data).

**Freshness probe** (cheap — the daily gate calls this first):
```python
from pe_monitor.fetch import fetch_asof
asof = fetch_asof("https://vhung-1.github.io/PEhistory/")  # GETs api.json, returns "2026-07-02"
```

**Full load** (only after the gate confirms new data):
```python
from pe_monitor.fetch import load_dashboard
dash = load_dashboard(base_url)   # GETs data.json + q_pairs.json
# -> Dashboard(asof, dates, pe, sector_of, sectors, pairs, base_url)
dash.latest_pe("RJF US")          # last non-null P/E for a ticker
```

`load_dashboard` returns a single `Dashboard` dataclass that the analytics layer
(`analyze.py`) reads — the network layer is fully isolated in `fetch.py`.

---

## 5. Freshness gating (why we hit `api.json` separately)

The daily job avoids re-downloading ~1 MB and re-emailing on unchanged data:

1. `pe_monitor check` → `fetch_asof()` reads `api.json`'s `asof` (~5 KB).
2. Compare to the last processed value stored in `state/last_asof.txt`.
3. Only if the `asof` changed does it call `load_dashboard()` and proceed to
   build + send.

So the heavy endpoints (`data.json`, `q_pairs.json`) are fetched **once per
genuine data refresh**, not on every scheduled run.

---

## 6. Failure behaviour

- Network / non-200 → `requests` raises, the CLI exits non-zero, the GitHub
  Action step fails visibly. No partial or stale email is sent.
- A ticker with no data yet (pre-listing) is `null` in `pe[TICKER]`; the
  analytics layer drops nulls before computing, so new listings simply don't
  generate signals until they have enough history.

---

## 7. Quick manual check

```bash
# snapshot date
curl -s https://vhung-1.github.io/PEhistory/api.json | python3 -c "import sys,json;print(json.load(sys.stdin)['asof'])"

# latest P/E for one name
curl -s https://vhung-1.github.io/PEhistory/data.json \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('RJF US', d['pe']['RJF US'][-1])"

# a pair's current deviation
curl -s https://vhung-1.github.io/PEhistory/q_pairs.json \
  | python3 -c "import sys,json;p=[x for x in json.load(sys.stdin) if x['a']=='LPLA US' and x['b']=='RJF US'][0];print(p['a'],p['b'],p['devnow'])"
```

---

*Data source: the public Relative-Value Forward-P/E dashboard. Not investment advice.*
