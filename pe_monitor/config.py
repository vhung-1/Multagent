"""Configuration for the PE-multiples monitoring agent.

Everything is driven by environment variables so the same code runs locally
and inside the GitHub Action. Defaults are sensible for the
diversified-financials forward-P/E dashboard.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _f(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v not in (None, "") else default


def _i(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v not in (None, "") else default


def _s(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


@dataclass
class Config:
    # ---- Data source -------------------------------------------------------
    base_url: str = field(default_factory=lambda: _s(
        "PE_BASE_URL", "https://vhung-1.github.io/PEhistory/"))

    # ---- Single-name dislocation thresholds (vs own PE history) ------------
    # Headline z-score is computed over a trailing window (falls back to full
    # history when the listing is younger than the window).
    single_lookback_days: int = field(default_factory=lambda: _i("SINGLE_LOOKBACK_DAYS", 756))
    single_min_history: int = field(default_factory=lambda: _i("SINGLE_MIN_HISTORY", 252))
    single_z: float = field(default_factory=lambda: _f("SINGLE_Z", 2.0))
    single_min_pct: float = field(default_factory=lambda: _f("SINGLE_MIN_PCT", 10.0))

    # ---- Pair-trade dislocation thresholds (from q_pairs.json) -------------
    pair_z: float = field(default_factory=lambda: _f("PAIR_Z", 2.0))
    pair_dev_pct: float = field(default_factory=lambda: _f("PAIR_DEV_PCT", 15.0))
    pair_ic_min: float = field(default_factory=lambda: _f("PAIR_IC_MIN", 0.30))
    pair_hit_min: float = field(default_factory=lambda: _f("PAIR_HIT_MIN", 60.0))
    pair_min_nq: int = field(default_factory=lambda: _i("PAIR_MIN_NQ", 6))

    # ---- How many alerts get a chart in the email -------------------------
    top_charts_single: int = field(default_factory=lambda: _i("TOP_CHARTS_SINGLE", 4))
    top_charts_pair: int = field(default_factory=lambda: _i("TOP_CHARTS_PAIR", 4))

    # ---- Output / chart hosting -------------------------------------------
    out_dir: str = field(default_factory=lambda: _s("OUT_DIR", "out"))
    charts_dir: str = field(default_factory=lambda: _s("CHARTS_DIR", "charts"))
    # "url"  -> reference charts by absolute URL (works in Gmail/Workspace);
    # "datauri" -> embed as base64 (self-contained, good for local preview).
    chart_mode: str = field(default_factory=lambda: _s("CHART_MODE", "url").lower())
    # Absolute base for chart URLs. In GitHub Actions this is derived from
    # GITHUB_REPOSITORY + GITHUB_REF_NAME if CHART_BASE_URL is unset.
    chart_base_url: str = field(default_factory=lambda: _s("CHART_BASE_URL", ""))

    # ---- Email (Brevo) -----------------------------------------------------
    brevo_api_key: str = field(default_factory=lambda: _s("BREVO_API_KEY", ""))
    mail_to: str = field(default_factory=lambda: _s("MAIL_TO", "vhung@attelascap.com"))
    mail_sender_email: str = field(default_factory=lambda: _s("MAIL_SENDER_EMAIL", "vhung@attelascap.com"))
    mail_sender_name: str = field(default_factory=lambda: _s("MAIL_SENDER_NAME", "PE Multiples Monitor"))
    # Send the email even when nothing breaches thresholds (a quiet "all clear").
    send_when_empty: bool = field(default_factory=lambda: _s("SEND_WHEN_EMPTY", "true").lower() == "true")

    def resolve_chart_base_url(self, asof: str) -> str:
        """Absolute base URL under which the day's charts will be reachable."""
        if self.chart_base_url:
            base = self.chart_base_url.rstrip("/")
        else:
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            ref = os.environ.get("GITHUB_REF_NAME", "main")
            if not repo:
                # No hosting context; caller should fall back to datauri.
                return ""
            base = f"https://raw.githubusercontent.com/{repo}/{ref}/{self.charts_dir}"
        return f"{base}/{asof}"

    @property
    def mail_recipients(self) -> list[str]:
        return [e.strip() for e in self.mail_to.split(",") if e.strip()]
