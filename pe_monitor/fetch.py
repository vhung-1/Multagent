"""Fetch the dashboard JSON endpoints."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

TIMEOUT = 30


@dataclass
class Dashboard:
    asof: str
    dates: list[str]
    pe: dict[str, list[float | None]]
    sector_of: dict[str, str]
    sectors: dict[str, list[str]]
    pairs: list[dict[str, Any]]
    base_url: str

    def latest_pe(self, ticker: str) -> float | None:
        for v in reversed(self.pe.get(ticker, [])):
            if v is not None:
                return v
        return None


def _get_json(url: str) -> Any:
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def load_dashboard(base_url: str) -> Dashboard:
    base = base_url.rstrip("/") + "/"
    data = _get_json(base + "data.json")
    pairs = _get_json(base + "q_pairs.json")
    return Dashboard(
        asof=data["asof"],
        dates=data["dates"],
        pe=data["pe"],
        sector_of=data.get("sector_of", {}),
        sectors=data.get("sectors", {}),
        pairs=pairs,
        base_url=base,
    )
