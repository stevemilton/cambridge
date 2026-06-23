# Wiring real connectors

The daemon runs continuously today, but against a **simulated** market and a
**mock** broker. To make it trade something real you swap exactly two objects.
Both have small, explicit interfaces — nothing else in the loop changes.

> Do this in stages: **paper/testnet first**, real data + paper broker next,
> real money last. The simulated connectors exist so you can prove the loop's
> behaviour before any of that.

---

## 1. Market data — replace `MarketDataConnector`

**File:** `quantloop/connectors/market_data.py`
**Interface the rest of the loop depends on:**

```python
class MyDataConnector:
    def fetch(self, lookback: int) -> dict[str, dict]:
        # return, per symbol:
        # {
        #   "SYMBOL": {
        #       "symbol":  "SYMBOL",
        #       "prices":  [float, ...],   # last `lookback` closes, oldest -> newest
        #       "volumes": [float, ...],   # same length as prices
        #       "flags":   {"fomc": bool, "near_earnings": bool},  # calendar blackouts
        #   },
        #   ...
        # }
```

That return shape is the *entire* contract. Build it from your vendor's
candle/OHLCV endpoint and hand it to `Pipeline(data=MyDataConnector(...))`.

**Providers that fit:**

| Asset class | Provider | Notes |
|---|---|---|
| Crypto | **Binance / Bybit / Kraken / Coinbase** via [`ccxt`](https://github.com/ccxt/ccxt) | One library, ~100 exchanges, free public candles. Easiest start. |
| Crypto perps | **Hyperliquid** API | Author's domain (HFT-style perps); good docs, REST + WS. |
| Prediction markets | **Kalshi**, **Polymarket** | The article's "prediction markets" — markets-as-symbols, prices are probabilities. |
| Equities | **Alpaca** (free tier), **Polygon.io**, **Databento** | Alpaca bundles data + a paper broker (see below). Polygon/Databento for deeper history. |
| Calendar flags | **FRED** (FOMC dates), **Finnhub / FMP** (earnings) | Populate `flags.fomc` / `flags.near_earnings`; the skill's blackout rules act on them. |

For low-latency or high-frequency use, hold a websocket feed and let `fetch()`
return the last `lookback` bars from an in-memory ring buffer rather than making
a REST call every cycle.

---

## 2. Broker — replace `BrokerConnector`

**File:** `quantloop/connectors/broker.py`
**Interface the rest of the loop depends on:**

```python
class MyBroker:
    def send_orders(self, signal: dict, price: float): ...   # place a verified order
    def get_positions(self) -> list[Position]: ...           # current open book
    def mark(self, prices: dict[str, float]) -> float: ...   # equity, marked to market
    def drawdown(self, prices: dict[str, float]) -> float: ...# peak-to-trough (>= 0)
    def close_all(self, prices: dict[str, float]) -> int: ...# the kill switch
```

`send_orders` and `close_all` are the only methods that touch real money;
`get_positions` / `mark` / `drawdown` feed the risk monitor. Keep the position
cap enforced *here* (as the mock does) so it's a hard limit, not just an agent
suggestion.

**Providers that fit:**

| Asset class | Provider | Paper trading? |
|---|---|---|
| Stocks + crypto | **Alpaca** | ✅ first-class paper account — start here |
| Crypto (spot/perps) | **Binance / Bybit / Hyperliquid** via `ccxt` | ✅ exchange testnets |
| Equities / futures / options | **Interactive Brokers** via [`ib_insync`](https://github.com/erdewit/ib_insync) | ✅ IB paper account |
| Prediction markets | **Kalshi**, **Polymarket** | Kalshi has a demo environment |

**Strongly recommended:** point `send_orders` at a **paper/testnet** endpoint
until you've watched the loop run for a while and trust its behaviour. Flipping
to live is then a one-line credential/URL change.

---

## On MCP

The article frames connectors as MCP servers. You can wrap either connector as
an MCP server and call it over the protocol — useful if you want the same feed
shared across tools/agents. For a single daemon, calling the vendor SDK directly
from inside the connector class (as above) is simpler and lower-latency; the MCP
layer buys you nothing extra here. Either way the loop only sees the two
interfaces above.

---

## Putting it together

```python
from quantloop.pipeline import Pipeline

pipe = Pipeline(backend="claude")          # real models
pipe.data   = MyDataConnector(api_key=...)  # real feed
pipe.broker = MyBroker(api_key=..., paper=True)  # paper broker first!

engine = pipe.serve(tick="1m", ingest_interval="1h", risk_interval="1m")
engine.run(max_cycles=None, real_time=True)   # the daemon
```

When all three are real (models, data, broker) and you've validated on paper,
that's the self-running system the article describes — running on your Hetzner
box, after the laptop is closed.
