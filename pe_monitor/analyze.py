"""Signal generation.

Two independent dislocation signals:

1. Single-name: how far each stock's current forward P/E sits from its OWN
   historical average, expressed as a z-score (and % deviation / percentile)
   over a trailing window.

2. Pair-trade: how far each relative-value pair's current P/E ratio sits from
   that pair's long-run average ratio. This is precomputed by the dashboard as
   `devnow` (= current ratio / mean ratio - 1, in %); we z-score it against the
   pair's own deviation history (`ser`) and gate on the pair's historical
   mean-reversion quality (information coefficient + hit rate).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import Config
from .fetch import Dashboard

ONE_YEAR = 252


@dataclass
class SingleAlert:
    ticker: str
    sector: str
    current: float
    mean_win: float       # mean over the lookback window
    std_win: float
    z: float
    pct: float            # % deviation of current vs window mean
    pctile: float         # percentile rank of current within window (0-100)
    mean_1y: float | None
    n: int                # number of observations in window
    window_label: str

    @property
    def direction(self) -> str:
        return "RICH" if self.z > 0 else "CHEAP"

    @property
    def abs_z(self) -> float:
        return abs(self.z)


@dataclass
class PairAlert:
    a: str
    b: str
    sector: str
    devnow: float         # current deviation of ratio a/b vs its average (%)
    z: float
    ser_mean: float
    ser_std: float
    ic: float
    hit: float
    nq: int
    avgq: float           # historical avg quarterly pair return (%)
    cum: float            # cumulative pair return (%)
    ser: list[dict[str, Any]]

    @property
    def long_leg(self) -> str:
        # devnow < 0: ratio a/b below average -> a is cheap vs b -> long a.
        return self.a if self.devnow < 0 else self.b

    @property
    def short_leg(self) -> str:
        return self.b if self.devnow < 0 else self.a

    @property
    def trade(self) -> str:
        return f"Long {self.long_leg} / Short {self.short_leg}"

    @property
    def abs_z(self) -> float:
        return abs(self.z)

    @property
    def score(self) -> float:
        # Reliability-weighted strength: how stretched, scaled by how reliably
        # this pair has mean-reverted historically.
        return abs(self.z) * max(self.ic, 0.0)


def _series(dash: Dashboard, ticker: str) -> np.ndarray:
    vals = dash.pe.get(ticker, [])
    arr = np.array([np.nan if v is None else float(v) for v in vals], dtype=float)
    return arr[~np.isnan(arr)]


def single_name_alerts(dash: Dashboard, cfg: Config) -> list[SingleAlert]:
    alerts: list[SingleAlert] = []
    for ticker in dash.pe:
        clean = _series(dash, ticker)
        if clean.size < cfg.single_min_history:
            continue
        current = float(clean[-1])
        if current <= 0:
            continue

        win = clean[-cfg.single_lookback_days:] if clean.size > cfg.single_lookback_days else clean
        full = clean.size <= cfg.single_lookback_days
        window_label = "full history" if full else f"{cfg.single_lookback_days // ONE_YEAR}y"

        mean = float(np.mean(win))
        std = float(np.std(win, ddof=1))
        if std == 0:
            continue
        z = (current - mean) / std
        pct = (current / mean - 1.0) * 100.0
        pctile = float((win <= current).mean() * 100.0)
        mean_1y = float(np.mean(clean[-ONE_YEAR:])) if clean.size >= ONE_YEAR else None

        if abs(z) >= cfg.single_z and abs(pct) >= cfg.single_min_pct:
            alerts.append(SingleAlert(
                ticker=ticker,
                sector=dash.sector_of.get(ticker, "—"),
                current=current, mean_win=mean, std_win=std, z=z, pct=pct,
                pctile=pctile, mean_1y=mean_1y, n=int(win.size),
                window_label=window_label,
            ))
    alerts.sort(key=lambda a: a.abs_z, reverse=True)
    return alerts


def pair_alerts(dash: Dashboard, cfg: Config) -> list[PairAlert]:
    alerts: list[PairAlert] = []
    for p in dash.pairs:
        ser = p.get("ser") or []
        devs = np.array([s["d"] for s in ser if s.get("d") is not None], dtype=float)
        if devs.size < 6:
            continue
        ser_mean = float(np.mean(devs))
        ser_std = float(np.std(devs, ddof=1))
        if ser_std == 0:
            continue
        devnow = float(p["devnow"])
        z = (devnow - ser_mean) / ser_std

        ic = float(p.get("ic", 0.0))
        hit = float(p.get("hit", 0.0))
        nq = int(p.get("nq", 0))

        quality = ic >= cfg.pair_ic_min and hit >= cfg.pair_hit_min and nq >= cfg.pair_min_nq
        stretched = abs(z) >= cfg.pair_z or abs(devnow) >= cfg.pair_dev_pct
        if quality and stretched:
            alerts.append(PairAlert(
                a=p["a"], b=p["b"], sector=p.get("sec", "—"),
                devnow=devnow, z=z, ser_mean=ser_mean, ser_std=ser_std,
                ic=ic, hit=hit, nq=nq,
                avgq=float(p.get("avgq", 0.0)), cum=float(p.get("cum", 0.0)),
                ser=ser,
            ))
    alerts.sort(key=lambda a: a.score, reverse=True)
    return alerts
