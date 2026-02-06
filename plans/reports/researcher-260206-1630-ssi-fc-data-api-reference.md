# SSI FastConnect Data (ssi-fc-data) API Research Report

**Date:** 2026-02-06
**Package:** `ssi-fc-data` v2.1.2
**Repository:** https://github.com/SSI-Securities-Corporation/python-fcdata
**PyPI:** https://pypi.org/project/ssi-fc-data/

## Executive Summary

SSI FastConnect Data (FC Data) provides real-time market data for Vietnamese securities markets (Cash & Derivatives) via REST APIs and WebSocket streaming. Library is **synchronous-only** — use `asyncio.to_thread()` for async integration.

## 1. Installation

```bash
pip install ssi-fc-data
```

## 2. Authentication & Configuration

### 2.1 Configuration File (`fcdata.json`)

Stores service connection credentials:

```json
{
  "auth_type": "Bearer",
  "consumerID": "<your-consumer-id>",
  "consumerSecret": "<your-consumer-secret>",
  "url": "https://fc-data.ssi.com.vn/",
  "stream_url": "https://fc-data.ssi.com.vn/"
}
```

**Credential Source:** Obtain `consumerID`, `consumerSecret`, and `PrivateKey` from SSI's iBoard platform after registering for FastConnect API service.

### 2.2 Load Config in Python

```python
import json

# Load config
with open('fcdata.json', 'r') as f:
    config = json.load(f)
```

## 3. Core Classes

### 3.1 `MarketDataClient`

**Import:**
```python
from ssi_fc_data.fc_md_client import MarketDataClient
```

**Constructor:**
```python
client = MarketDataClient(config)
```

**Purpose:** Execute REST API calls (securities list, securities details, etc.)

**Example Usage:**
```python
from ssi_fc_data.fc_md_client import MarketDataClient
from ssi_fc_data.fc_md_model import GetSecuritiesListRequest

client = MarketDataClient(config)

# Get securities list
req = GetSecuritiesListRequest(market='VN30')
response = client.securities(config, req)
print(response)

# Get securities details
details_req = GetSecuritiesDetailsRequest(symbols=['HPG', 'VNM'])
details = client.securities_details(config, details_req)
print(details)
```

### 3.2 `MarketDataStream`

**Import:**
```python
from ssi_fc_data.fc_md_stream import MarketDataStream
```

**Constructor:**
```python
stream = MarketDataStream(config, MarketDataClient(config))
```

**Purpose:** Establish WebSocket connection for real-time streaming data.

## 4. Streaming API

### 4.1 Method Signature: `start()`

```python
stream.start(on_message_callback, on_error_callback, channel)
```

**Parameters:**
- `on_message_callback`: Function receiving market data messages
- `on_error_callback`: Function receiving error messages
- `channel`: String specifying subscription channel(s)

### 4.2 Callback Signatures

**Message Callback:**
```python
def get_market_data(message):
    """
    Args:
        message: JSON object/dict with market data fields
    Returns:
        None
    """
    print(message)
```

**Error Callback:**
```python
def getError(error):
    """
    Args:
        error: Error message/object
    Returns:
        None
    """
    print(error)
```

### 4.3 Full Streaming Example

```python
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient
import json

# Load config
with open('fcdata.json', 'r') as f:
    config = json.load(f)

# Define callbacks
def get_market_data(message):
    print(message)

def getError(error):
    print(error)

# Create stream
stream = MarketDataStream(config, MarketDataClient(config))

# Start streaming (blocking call)
selected_channel = "X"  # Channel X = securities market data
stream.start(get_market_data, getError, selected_channel)

# Stream runs in loop until exit() command
```

## 5. Streaming Channels

| Channel | Description | Data Type |
|---------|-------------|-----------|
| `ALL` | All channels | Combined |
| `F` | Securities Status | Status updates |
| `X` | Market Data | Real-time quotes/trades |
| `R` | Foreign Room | Foreign ownership limits |
| `MI` | Index Data | Index values |
| `B` | RealTime Bar | OHLC information |

**Most Common:** Channel `X` for real-time securities market data.

## 6. Message Format

### 6.1 Message Structure (JSON)

```json
{
  "data": { ... },
  "uniqueid": "string",
  "connectionid": "string",
  "ipaddress": "string",
  "notifyevent": "string"
}
```

### 6.2 Channel X (Securities) Fields

**Per SSI FastConnect API Specs:**

| Field | Type | Description |
|-------|------|-------------|
| `StockNo` | Number | Security code (numeric form) |
| `Symbol` | String | Security code (symbol) |
| `LastPrice` | Number | Latest matched price |
| `LastVol` | Number | **Latest matched volume (per-trade, NOT cumulative)** |
| `TotalVol` | Number | Total cumulative volume |
| `BidPrice1` - `BidPrice10` | Number | Bid prices (10 levels) |
| `BidVol1` - `BidVol10` | Number | Bid volumes (10 levels) |
| `AskPrice1` - `AskPrice10` | Number | Ask prices (10 levels) |
| `AskVol1` - `AskVol10` | Number | Ask volumes (10 levels) |
| `MatchVol` | Number | Match volume indicator |

**Critical Note:** `LastVol` represents the **volume of the individual trade**, not cumulative total. Use `TotalVol` for cumulative volume.

### 6.3 `notify_id` Parameter

- `notify_id = 0`: Returns **all messages from beginning of day** (replay)
- `notify_id = -1`: Returns **only updates after connection** (live-only)

## 7. Async Integration Pattern

`ssi-fc-data` is **synchronous-only**. For async FastAPI integration:

```python
import asyncio
from ssi_fc_data.fc_md_stream import MarketDataStream
from ssi_fc_data.fc_md_client import MarketDataClient

async def run_stream():
    # Run synchronous stream in thread pool
    await asyncio.to_thread(
        stream.start,
        on_message_callback,
        on_error_callback,
        "X"
    )
```

## 8. Key Constraints

1. **Synchronous Library:** No native async support — wrap in `asyncio.to_thread()`
2. **Blocking Start:** `stream.start()` blocks until exit command
3. **Config Required:** Cannot instantiate without valid config object
4. **Credentials Required:** Must obtain from SSI iBoard (no trial/public access)
5. **VN Market Only:** Designed for Vietnamese stock exchanges (HOSE, HNX, UPCOM)

## 9. Related Repositories

- **Python REST + Streaming:** https://github.com/SSI-Securities-Corporation/python-fcdata
- **Python Trading:** https://github.com/SSI-Securities-Corporation/python-fctrading
- **Java Data:** https://github.com/SSI-Securities-Corporation/java-fcdata
- **Node.js Trading:** https://github.com/SSI-Securities-Corporation/node-fctrading
- **Official Docs:** https://guide.ssi.com.vn/ssi-products/fastconnect-data

## 10. Implementation Checklist

- [x] Load `fcdata.json` with valid credentials
- [x] Import `MarketDataClient` from `ssi_fc_data.fc_md_client`
- [x] Import `MarketDataStream` from `ssi_fc_data.fc_md_stream`
- [x] Create client: `MarketDataClient(config)`
- [x] Create stream: `MarketDataStream(config, client)`
- [x] Define `on_message(message)` callback
- [x] Define `on_error(error)` callback
- [x] Call `stream.start(on_message, on_error, channel)`
- [x] Use `asyncio.to_thread()` for async wrapping
- [x] Parse `message['data']` for market fields
- [x] Use `LastVol` for per-trade volume (not cumulative)

## Unresolved Questions

1. **Reconnection Logic:** No docs on auto-reconnect — implement manual retry?
2. **Exit Mechanism:** README mentions `exit()` command — how to trigger programmatically in daemon/background mode?
3. **Message Rate Limiting:** Max messages/sec per subscription not documented
4. **Channel Combinations:** Can multiple channels be passed as comma-separated string (`"X,MI"`) or requires separate connections?
5. **Thread Safety:** Is single `MarketDataStream` instance safe for concurrent callback execution, or need mutex?

---

**Sources:**
- [SSI-Securities-Corporation/python-fcdata](https://github.com/SSI-Securities-Corporation/python-fcdata)
- [ssi-fc-data PyPI](https://pypi.org/project/ssi-fc-data/)
- [FastConnect API Guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data)
- [Sample Client Guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide)
- [API Specs](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs)
- [Data Streaming Docs (Vietnamese)](https://guide.ssi.com.vn/ssi-products/tieng-viet/fastconnect-data/du-lieu-streaming)
