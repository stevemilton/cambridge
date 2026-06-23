"""Piece #6 — The connectors.

A loop that can only read files is a tiny loop. Connectors give it hands: a
market-data feed to read from and a broker to send orders to. In production
these sit behind the Model Context Protocol (MCP) so the same loop can hit a
real data vendor, a real broker, a database, or Slack. Here they are simulated
so the loop runs end to end and deterministically.
"""

from .market_data import MarketDataConnector
from .broker import BrokerConnector, Position

__all__ = ["MarketDataConnector", "BrokerConnector", "Position"]
