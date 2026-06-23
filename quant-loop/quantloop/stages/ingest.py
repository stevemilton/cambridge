"""Stage 1 — Data ingestion.

    @loop(interval="1h")
    def ingest_data():
        data = fetch_market_data(symbols=universe, lookback="30d")
        state.write("latest_data.parquet", data)

An automation fires on a cadence, pulls market data, and writes it to the shared
state file the next stage reads. Returns the fetched payload so the pipeline can
emit a `data_updated` event.
"""

from __future__ import annotations

from typing import Any

from ..connectors import MarketDataConnector
from ..state import State


def ingest(state: State, data: MarketDataConnector, lookback: int = 60) -> dict[str, Any]:
    payload = data.fetch(lookback=lookback)
    state.write("latest_data", payload)
    symbols = ", ".join(payload.keys())
    state.append(f"INGEST: pulled {lookback} bars for {len(payload)} symbol(s) [{symbols}]")
    return payload
