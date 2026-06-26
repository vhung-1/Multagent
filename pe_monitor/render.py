"""Render the digestible HTML email summary.

Inline styles only (email clients strip <style>/external CSS). Charts are
referenced via a caller-supplied id -> src map so the same template works for
both hosted-URL and embedded-base64 modes.
"""
from __future__ import annotations

import html

from .analyze import PairAlert, SingleAlert
from .config import Config
from .fetch import Dashboard

FONT = "-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"


def chart_id_single(a: SingleAlert) -> str:
    return "single_" + a.ticker.replace(" ", "_")


def chart_id_pair(p: PairAlert) -> str:
    return "pair_" + p.a.replace(" ", "_") + "__" + p.b.replace(" ", "_")


def _esc(s: str) -> str:
    return html.escape(str(s))


def _badge(text: str, color: str) -> str:
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            f'font-size:11px;font-weight:700;color:#fff;background:{color}">{text}</span>')


def _section_title(text: str, sub: str = "") -> str:
    s = (f'<tr><td style="padding:26px 0 6px"><div style="font:700 17px {FONT};'
         f'color:#1f2933">{text}</div>')
    if sub:
        s += f'<div style="font:400 12px {FONT};color:#7b8794;margin-top:2px">{sub}</div>'
    return s + "</td></tr>"


def _img_block(src: str, alt: str) -> str:
    if not src:
        return ""
    return (f'<tr><td style="padding:8px 0">'
            f'<img src="{_esc(src)}" alt="{_esc(alt)}" width="540" '
            f'style="display:block;width:100%;max-width:540px;height:auto;'
            f'border:1px solid #e6eaee;border-radius:8px"/></td></tr>')


def _single_table(alerts: list[SingleAlert]) -> str:
    head = ("<tr>" + "".join(
        f'<th style="text-align:{al};font:700 11px {FONT};color:#7b8794;'
        f'padding:6px 8px;border-bottom:2px solid #e6eaee;text-transform:uppercase">{h}</th>'
        for h, al in [("Ticker", "left"), ("Sector", "left"), ("Signal", "left"),
                      ("P/E now", "right"), (f"Avg", "right"), ("% dev", "right"),
                      ("z-score", "right"), ("%ile", "right")]) + "</tr>")
    rows = []
    for a in alerts:
        color = "#dc2626" if a.z > 0 else "#059669"
        rows.append(
            "<tr>"
            f'<td style="font:700 12px {FONT};color:#1f2933;padding:7px 8px;border-bottom:1px solid #eef1f4">{_esc(a.ticker)}</td>'
            f'<td style="font:400 12px {FONT};color:#52606d;padding:7px 8px;border-bottom:1px solid #eef1f4">{_esc(a.sector)}</td>'
            f'<td style="padding:7px 8px;border-bottom:1px solid #eef1f4">{_badge(a.direction, color)}</td>'
            f'<td style="font:600 12px {FONT};color:#1f2933;text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{a.current:.1f}x</td>'
            f'<td style="font:400 12px {FONT};color:#52606d;text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{a.mean_win:.1f}x</td>'
            f'<td style="font:600 12px {FONT};color:{color};text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{a.pct:+.0f}%</td>'
            f'<td style="font:700 12px {FONT};color:{color};text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{a.z:+.1f}σ</td>'
            f'<td style="font:400 12px {FONT};color:#52606d;text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{a.pctile:.0f}</td>'
            "</tr>")
    return (f'<tr><td><table cellpadding="0" cellspacing="0" width="100%" '
            f'style="border-collapse:collapse">{head}{"".join(rows)}</table></td></tr>')


def _pair_table(alerts: list[PairAlert]) -> str:
    head = ("<tr>" + "".join(
        f'<th style="text-align:{al};font:700 11px {FONT};color:#7b8794;'
        f'padding:6px 8px;border-bottom:2px solid #e6eaee;text-transform:uppercase">{h}</th>'
        for h, al in [("Pair", "left"), ("Suggested trade", "left"), ("Dev now", "right"),
                      ("z-score", "right"), ("IC", "right"), ("Hit", "right")]) + "</tr>")
    rows = []
    for p in alerts:
        color = "#dc2626" if p.devnow > 0 else "#059669"
        rows.append(
            "<tr>"
            f'<td style="font:700 12px {FONT};color:#1f2933;padding:7px 8px;border-bottom:1px solid #eef1f4">{_esc(p.a)} / {_esc(p.b)}</td>'
            f'<td style="font:600 12px {FONT};color:#2563eb;padding:7px 8px;border-bottom:1px solid #eef1f4">{_esc(p.trade)}</td>'
            f'<td style="font:600 12px {FONT};color:{color};text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{p.devnow:+.1f}%</td>'
            f'<td style="font:700 12px {FONT};color:{color};text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{p.z:+.1f}σ</td>'
            f'<td style="font:400 12px {FONT};color:#52606d;text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{p.ic:.2f}</td>'
            f'<td style="font:400 12px {FONT};color:#52606d;text-align:right;padding:7px 8px;border-bottom:1px solid #eef1f4">{p.hit:.0f}%</td>'
            "</tr>")
    return (f'<tr><td><table cellpadding="0" cellspacing="0" width="100%" '
            f'style="border-collapse:collapse">{head}{"".join(rows)}</table></td></tr>')


def render_email(dash: Dashboard, single: list[SingleAlert], pairs: list[PairAlert],
                 cfg: Config, chart_src: dict[str, str]) -> tuple[str, str]:
    n_rich = sum(1 for a in single if a.z > 0)
    n_cheap = len(single) - n_rich
    subject = (f"PE Monitor {dash.asof}: {len(single)} name + {len(pairs)} pair "
               f"dislocations")

    summary = (
        f'<tr><td style="padding:4px 0 0">'
        f'<div style="font:400 13px {FONT};color:#52606d;line-height:1.5">'
        f'<b style="color:#1f2933">{len(single)}</b> single-name dislocations '
        f'(<span style="color:#dc2626">{n_rich} rich</span>, '
        f'<span style="color:#059669">{n_cheap} cheap</span>) and '
        f'<b style="color:#1f2933">{len(pairs)}</b> high-quality pair dislocations '
        f'breached thresholds across the {len(dash.pe)}-name universe.'
        f'</div></td></tr>')

    parts: list[str] = []

    # ---- single-name section ----
    if single:
        parts.append(_section_title(
            "Single-name vs own P/E history",
            f"Current forward P/E ≥ {cfg.single_z:.0f}σ and ≥ {cfg.single_min_pct:.0f}% "
            f"from the {single[0].window_label} average."))
        for a in single[:cfg.top_charts_single]:
            parts.append(_img_block(chart_src.get(chart_id_single(a), ""),
                                    f"{a.ticker} P/E history"))
        parts.append(_single_table(single))
    else:
        parts.append(_section_title("Single-name vs own P/E history",
                                    "No names breached thresholds today."))

    # ---- pair section ----
    if pairs:
        parts.append(_section_title(
            "Pair-trade dislocations",
            f"Reliable pairs (IC ≥ {cfg.pair_ic_min:.2f}, hit ≥ {cfg.pair_hit_min:.0f}%) "
            f"whose P/E ratio is ≥ {cfg.pair_z:.0f}σ or ≥ {cfg.pair_dev_pct:.0f}% from its average."))
        for p in pairs[:cfg.top_charts_pair]:
            parts.append(_img_block(chart_src.get(chart_id_pair(p), ""),
                                    f"{p.a}/{p.b} ratio history"))
        parts.append(_pair_table(pairs))
    else:
        parts.append(_section_title("Pair-trade dislocations",
                                    "No high-quality pairs breached thresholds today."))

    footer = (
        f'<tr><td style="padding:28px 0 0;border-top:1px solid #e6eaee">'
        f'<div style="font:400 11px {FONT};color:#9aa5b1;line-height:1.6">'
        f'<b>Method.</b> Single-name z-score = (current P/E − trailing-window mean) / σ. '
        f'Pair deviation = current P/E ratio (A/B) vs its long-run average; z-scored against '
        f'the pair’s own deviation history. Pairs gated on historical mean-reversion quality '
        f'(information coefficient &amp; quarterly hit rate). Long leg = the relatively cheap side. '
        f'Not investment advice.<br/>'
        f'Source: <a href="{_esc(dash.base_url)}Relative_PE_Dashboard.html" '
        f'style="color:#2563eb">interactive dashboard</a> · data as of {dash.asof}.'
        f'</div></td></tr>')

    body = "".join(parts)
    return subject, f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f4f6f8">
<table cellpadding="0" cellspacing="0" width="100%" style="background:#f4f6f8;padding:24px 0">
<tr><td align="center">
<table cellpadding="0" cellspacing="0" width="600" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;padding:28px 30px;box-shadow:0 1px 3px rgba(16,24,40,0.06)">
<tr><td>
<div style="font:800 20px {FONT};color:#1f2933">PE Multiples Monitor</div>
<div style="font:500 13px {FONT};color:#7b8794;margin-top:2px">Diversified Financials · forward P/E · as of {dash.asof}</div>
</td></tr>
{summary}
{body}
{footer}
</table>
</td></tr>
</table>
</body></html>"""
