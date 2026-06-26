"""Chart rendering (matplotlib, Agg backend -> PNG).

One chart per flagged single-name dislocation (P/E history with mean +/- band)
and one per flagged pair (deviation-from-average history with band). Charts are
written to disk; the email references them either by absolute URL or, in
`datauri` mode, embeds them as base64.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .analyze import PairAlert, SingleAlert  # noqa: E402
from .fetch import Dashboard  # noqa: E402

plt.rcParams.update({
    "figure.dpi": 110,
    "font.size": 9,
    "axes.edgecolor": "#cbd2d9",
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "grid.color": "#e6eaee",
    "grid.linewidth": 0.7,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

INK = "#1f2933"
BLUE = "#2563eb"
RED = "#dc2626"
GREEN = "#059669"
MUTED = "#7b8794"


def _parse_dates(strs: list[str]) -> np.ndarray:
    return np.array([datetime.strptime(s, "%Y-%m-%d") for s in strs])


def single_chart(dash: Dashboard, a: SingleAlert, path: str) -> None:
    vals = dash.pe.get(a.ticker, [])
    dates = _parse_dates(dash.dates)
    arr = np.array([np.nan if v is None else float(v) for v in vals], dtype=float)
    mask = ~np.isnan(arr)
    x, y = dates[mask], arr[mask]

    fig, ax = plt.subplots(figsize=(5.4, 2.7))
    ax.plot(x, y, color=BLUE, lw=1.3, label="Forward P/E")
    ax.axhline(a.mean_win, color=MUTED, lw=1.0, ls="--",
               label=f"{a.window_label} avg {a.mean_win:.1f}x")
    ax.axhspan(a.mean_win - a.std_win, a.mean_win + a.std_win,
               color=MUTED, alpha=0.12, lw=0)
    ax.axhspan(a.mean_win - 2 * a.std_win, a.mean_win + 2 * a.std_win,
               color=MUTED, alpha=0.06, lw=0)

    dot = RED if a.z > 0 else GREEN
    ax.scatter([x[-1]], [y[-1]], color=dot, s=28, zorder=5)
    ax.annotate(f"{a.current:.1f}x ({a.z:+.1f}σ)",
                xy=(x[-1], y[-1]), xytext=(-6, 8),
                textcoords="offset points", ha="right",
                color=dot, fontsize=8.5, fontweight="bold")

    ax.set_title(f"{a.ticker}  —  {a.direction} vs {a.window_label} average",
                 color=INK, fontsize=10, fontweight="bold", loc="left")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="best", fontsize=7.5, frameon=False)
    ax.tick_params(colors=MUTED, labelsize=7.5)
    fig.tight_layout(pad=0.6)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def pair_chart(p: PairAlert, path: str) -> None:
    ser = [s for s in p.ser if s.get("d") is not None]
    x = np.array([datetime.strptime(s["t"], "%Y-%m") for s in ser])
    y = np.array([float(s["d"]) for s in ser])

    fig, ax = plt.subplots(figsize=(5.4, 2.7))
    ax.plot(x, y, color=BLUE, lw=1.3)
    ax.axhline(0, color=INK, lw=0.9)
    ax.axhline(p.ser_mean, color=MUTED, lw=1.0, ls="--",
               label=f"avg {p.ser_mean:+.1f}%")
    ax.axhspan(p.ser_mean - p.ser_std, p.ser_mean + p.ser_std,
               color=MUTED, alpha=0.12, lw=0)
    ax.axhspan(p.ser_mean - 2 * p.ser_std, p.ser_mean + 2 * p.ser_std,
               color=MUTED, alpha=0.06, lw=0)

    dot = RED if p.devnow > 0 else GREEN
    ax.scatter([x[-1]], [y[-1]], color=dot, s=28, zorder=5)
    ax.annotate(f"{p.devnow:+.1f}% ({p.z:+.1f}σ)",
                xy=(x[-1], y[-1]), xytext=(-6, 8),
                textcoords="offset points", ha="right",
                color=dot, fontsize=8.5, fontweight="bold")

    ax.set_title(f"{p.a} / {p.b}  —  P/E ratio vs history",
                 color=INK, fontsize=10, fontweight="bold", loc="left")
    ax.set_ylabel("dev. from avg ratio (%)", fontsize=7.5, color=MUTED)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="best", fontsize=7.5, frameon=False)
    ax.tick_params(colors=MUTED, labelsize=7.5)
    fig.tight_layout(pad=0.6)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def to_data_uri(path: str) -> str:
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
