"""CLI entry point.

Commands:
  build  fetch data, compute signals, render charts + out/email.html
  send   send the previously built email via Brevo
  run    build then send in one process (handy locally / with datauri charts)

The GitHub Action runs `build`, commits the charts so their URLs go live, then
runs `send`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import analyze, charts, render
from .brevo import send_email
from .config import Config
from .fetch import load_dashboard


def _build(cfg: Config) -> dict:
    dash = load_dashboard(cfg.base_url)
    single = analyze.single_name_alerts(dash, cfg)
    pairs = analyze.pair_alerts(dash, cfg)
    print(f"as of {dash.asof}: {len(single)} single-name, {len(pairs)} pair dislocations")

    charts_day_dir = os.path.join(cfg.charts_dir, dash.asof)
    charts.ensure_dir(charts_day_dir)
    charts.ensure_dir(cfg.out_dir)

    chart_files: dict[str, str] = {}  # chart_id -> file path

    for a in single[:cfg.top_charts_single]:
        cid = render.chart_id_single(a)
        fp = os.path.join(charts_day_dir, cid + ".png")
        charts.single_chart(dash, a, fp)
        chart_files[cid] = fp

    for p in pairs[:cfg.top_charts_pair]:
        cid = render.chart_id_pair(p)
        fp = os.path.join(charts_day_dir, cid + ".png")
        charts.pair_chart(p, fp)
        chart_files[cid] = fp

    # Resolve how the email references each chart.
    mode = cfg.chart_mode
    base = cfg.resolve_chart_base_url(dash.asof) if mode == "url" else ""
    if mode == "url" and not base:
        print("WARNING: chart_mode=url but no CHART_BASE_URL / GITHUB_REPOSITORY; "
              "falling back to embedded data URIs.", file=sys.stderr)
        mode = "datauri"

    chart_src: dict[str, str] = {}
    for cid, fp in chart_files.items():
        if mode == "url":
            chart_src[cid] = f"{base}/{os.path.basename(fp)}"
        else:
            chart_src[cid] = charts.to_data_uri(fp)

    subject, html = render.render_email(dash, single, pairs, cfg, chart_src)

    html_path = os.path.join(cfg.out_dir, "email.html")
    with open(html_path, "w") as fh:
        fh.write(html)
    meta = {"subject": subject, "asof": dash.asof,
            "n_single": len(single), "n_pairs": len(pairs)}
    with open(os.path.join(cfg.out_dir, "meta.json"), "w") as fh:
        json.dump(meta, fh)

    print(f"wrote {html_path} ({len(chart_files)} charts under {charts_day_dir})")
    return meta


def _send(cfg: Config) -> None:
    out = cfg.out_dir
    with open(os.path.join(out, "meta.json")) as fh:
        meta = json.load(fh)
    with open(os.path.join(out, "email.html")) as fh:
        html = fh.read()

    if meta["n_single"] == 0 and meta["n_pairs"] == 0 and not cfg.send_when_empty:
        print("No dislocations and SEND_WHEN_EMPTY=false; skipping email.")
        return

    res = send_email(cfg.brevo_api_key, cfg.mail_sender_email, cfg.mail_sender_name,
                     cfg.mail_recipients, meta["subject"], html)
    print(f"sent to {', '.join(cfg.mail_recipients)}: {res}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pe_monitor")
    parser.add_argument("command", choices=["build", "send", "run"])
    args = parser.parse_args(argv)
    cfg = Config()

    if args.command == "build":
        _build(cfg)
    elif args.command == "send":
        _send(cfg)
    else:  # run
        _build(cfg)
        _send(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
