# System Architecture

## High-Level Overview

```mermaid
graph TB
    SSI[SSI FastConnect<br/>WebSocket + REST] -->|Real-time feeds| Backend

    subgraph Backend[FastAPI Backend :8000]
        MDP[MarketDataProcessor]
        MDP --> QC[QuoteCache]
        MDP --> TC[TradeClassifier]
        MDP --> SA[SessionAggregator]
        MDP --> FIT[ForeignInvestorTracker]
        MDP --> IT[IndexTracker]
        MDP --> DT[DerivativesTracker]

        TC --> PT[PriceTracker]
        PT --> AS[AlertService]

        DP[DataPublisher] --> WS[WebSocket Router]
        MR[Market Router] --> REST[REST API]
        HR[History Router] --> REST

        DB[(TimescaleDB)]
        BW[BatchWriter] --> DB
        HS[HistoryService] --> DB
    end

    subgraph Frontend[React Frontend :80]
        PB[Price Board]
        FF[Foreign Flow]
        VA[Volume Analysis]
        DP2[Derivatives Panel]
        SIG[Signals Page]
    end

    subgraph Nginx[Nginx :80]
        direction LR
        N1["/ → Frontend"]
        N2["/api/* → Backend"]
        N3["/ws/* → Backend WS"]
    end

    Nginx --> Frontend
    Nginx --> Backend
    Frontend -->|WS + REST| Nginx

    subgraph Monitoring
        PROM[Prometheus :9090]
        GRAF[Grafana :3000]
        NE[Node Exporter :9100]
    end

    PROM -->|scrape /metrics| Backend
    PROM -->|scrape| NE
    GRAF -->|query| PROM
```

## Data Flow

```mermaid
sequenceDiagram
    participant SSI as SSI FastConnect
    participant MDP as MarketDataProcessor
    participant Services as Processing Services
    participant DP as DataPublisher
    participant WS as WebSocket Clients
    participant REST as REST Clients
    participant DB as TimescaleDB

    SSI->>MDP: X-TRADE message
    MDP->>Services: Route by message type

    Note over Services: TradeClassifier → buy/sell/neutral<br/>SessionAggregator → per-phase volume<br/>ForeignInvestorTracker → delta + speed<br/>IndexTracker → VN30/VNINDEX<br/>DerivativesTracker → basis calc

    Services->>DP: State updated (event-driven)
    DP->>WS: Throttled broadcast (500ms)

    Services->>DB: BatchWriter (async insert)
    REST->>DB: HistoryService queries

    Note over DP,WS: 4 channels: market, foreign, index, alerts
```

## Message Routing

```mermaid
flowchart LR
    MSG[SSI Message] --> TYPE{Message Type}

    TYPE -->|X-TRADE| TC[TradeClassifier]
    TYPE -->|X-Quote| QC[QuoteCache]
    TYPE -->|R:ALL| FIT[ForeignInvestorTracker]
    TYPE -->|MI:VN30| IT[IndexTracker]
    TYPE -->|MI:VNINDEX| IT
    TYPE -->|VN30F trade| DT[DerivativesTracker]

    TC --> SA[SessionAggregator]
    TC --> PT[PriceTracker]
    PT -->|anomaly| AS[AlertService]

    AS -->|broadcast| ALERT[/ws/alerts]
```

## Backend Services

| Service | Responsibility | Input | Output |
|---------|---------------|-------|--------|
| `SsiAuthService` | OAuth2 token management | Consumer ID/Secret | Access token |
| `SsiMarketService` | REST lookups (VN30 components, securities) | Token | Market data |
| `SsiStreamService` | WebSocket connection + reconnect | Token | Raw messages |
| `SsiFieldNormalizer` | SSI field name → standard names | Raw dict | Normalized dict |
| `FuturesResolver` | Determine active VN30F contract | Date | Contract symbol |
| `QuoteCache` | Bid/ask price storage | Quote messages | Latest quotes |
| `TradeClassifier` | Classify trades as buy/sell/neutral using `LastVol` | Trade + quotes | ClassifiedTrade |
| `SessionAggregator` | Volume accumulation per session phase | ClassifiedTrade | SessionStats |
| `ForeignInvestorTracker` | Delta, speed, acceleration per symbol | R channel | ForeignInvestorData |
| `IndexTracker` | VN30/VNINDEX real-time values | MI messages | IndexData |
| `DerivativesTracker` | Futures price, basis vs spot | VN30F trades | DerivativesData |
| `PriceTracker` | 4 signal detectors (volume, price, foreign, basis) | All services | Alert triggers |
| `AlertService` | Dedup + buffer + WS broadcast | Alert triggers | Alert stream |

## Frontend Architecture

```mermaid
graph TB
    subgraph Pages
        PB[PriceBoardPage]
        FF[ForeignFlowPage]
        VA[VolumeAnalysisPage]
        DP[DerivativesPage]
        SIG[SignalsPage]
    end

    subgraph Hooks
        UWS[useWebSocket<br/>auto-reconnect + REST fallback]
        UMS[useMarketSnapshot]
        UFF[useForeignFlow<br/>hybrid WS+REST]
        UDD[useDerivativesData]
        UAL[useAlerts]
        UVS[useVolumeStats]
    end

    subgraph Transport
        WS[WebSocket /ws/*]
        API[REST /api/*]
    end

    PB --> UWS
    FF --> UFF
    VA --> UVS
    DP --> UDD
    SIG --> UAL

    UWS --> WS
    UFF --> WS
    UFF --> API
    UMS --> API
    UDD --> API
    UAL --> WS
    UVS --> API
```

### Hybrid Data Strategy

| Channel | Transport | Update Freq | Payload |
|---------|-----------|-------------|---------|
| Market snapshot | WebSocket `/ws/market` | 500ms throttle | Quotes + indices + foreign summary |
| Foreign detail | REST `/api/market/foreign-detail` | 10s polling | Full per-symbol breakdown |
| Derivatives basis | REST `/api/market/basis-trend` | 10s polling | Historical basis points |
| Alerts | WebSocket `/ws/alerts` | Real-time | Alert objects |
| Volume stats | REST `/api/market/volume-stats` | 10s polling | Per-symbol session stats |

## Database Schema

```mermaid
erDiagram
    trade_ticks {
        timestamptz time PK
        varchar symbol
        float price
        int volume
        varchar trade_type
        varchar session
    }

    ohlcv_1m {
        timestamptz time PK
        varchar symbol
        float open
        float high
        float low
        float close
        bigint volume
        bigint buy_volume
        bigint sell_volume
    }

    foreign_flow {
        timestamptz time PK
        varchar symbol
        bigint buy_vol
        bigint sell_vol
        bigint net_vol
        float speed
    }

    index_history {
        timestamptz time PK
        varchar index_name
        float value
        float change
        float change_pct
        bigint volume
    }

    derivatives_history {
        timestamptz time PK
        varchar contract
        float price
        float basis
        int open_interest
    }
```

All tables use TimescaleDB hypertables with automatic time-based partitioning.

## Deployment Architecture

```mermaid
graph TB
    Internet[Internet :80] --> Nginx

    subgraph Docker[Docker Compose Network]
        Nginx[Nginx<br/>Reverse Proxy]

        Nginx -->|"/"| FE[Frontend<br/>React + Nginx<br/>128MB]
        Nginx -->|"/api/*"| BE[Backend<br/>FastAPI + uvloop<br/>1GB]
        Nginx -->|"/ws/*"| BE
        Nginx -->|"/health"| BE

        BE --> DB[(TimescaleDB<br/>PostgreSQL 16<br/>1GB)]
        BE -->|"/metrics"| PROM[Prometheus<br/>15d retention<br/>512MB]

        NE[Node Exporter] --> PROM
        PROM --> GRAF[Grafana<br/>4 dashboards<br/>256MB]
    end

    subgraph External
        SSI[SSI FastConnect<br/>WebSocket]
    end

    BE <-->|Real-time feeds| SSI
```

## Session Phases

VN stock market operates in distinct phases:

| Phase | Time (ICT) | Trading |
|-------|-----------|---------|
| Pre-open | 09:00-09:15 | ATO auction |
| Morning | 09:15-11:30 | Continuous |
| Lunch | 11:30-13:00 | Closed |
| Afternoon | 13:00-14:30 | Continuous |
| Close | 14:30-14:45 | ATC auction |
| Post-close | 14:45-15:00 | Put-through |

Trades are tagged with session phase for per-phase volume breakdown.

## Alert Types

| Alert | Trigger | Severity |
|-------|---------|----------|
| `VOLUME_SPIKE` | Volume >3x 5-min average | WARNING/CRITICAL |
| `PRICE_BREAKOUT` | Price crosses key levels | WARNING |
| `FOREIGN_ACCELERATION` | Foreign speed change >2σ | WARNING/CRITICAL |
| `BASIS_DIVERGENCE` | Futures-spot spread anomaly | WARNING |

Alerts are deduplicated (60s cooldown per symbol+type) and broadcast via `/ws/alerts`.

## Performance Characteristics

| Component | Metric | Value |
|-----------|--------|-------|
| MarketDataProcessor | Throughput | 58,874 msg/s |
| TradeClassifier | Latency | <1ms |
| ForeignInvestorTracker | Latency | <0.5ms |
| DataPublisher | WS broadcast | 500ms throttle |
| BatchWriter | DB insert | Async batch (1s window) |
| WebSocket | p99 latency | 85-95ms |
| REST API | p95 latency | 175-195ms |
