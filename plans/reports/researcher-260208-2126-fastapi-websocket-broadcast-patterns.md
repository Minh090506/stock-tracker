# FastAPI WebSocket Broadcast Server Patterns (2025-2026)

**Research Date:** 2026-02-08
**Focus:** ConnectionManager, room/channel subscriptions, heartbeat, broadcast efficiency, asyncio integration, lifecycle, error handling

---

## 1. ConnectionManager Pattern

### Basic Structure
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()  # MUST await before send/receive
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)
```

### Key Points
- **MUST** `await websocket.accept()` before any send/receive operations
- Single-process only — in-memory list works while process runs
- For multi-process: use Redis pub/sub, PostgreSQL, or `encode/broadcaster`

---

## 2. Room/Channel Subscription Pattern

### Room-Based Manager
```python
class RoomManager:
    def __init__(self):
        # Map room_id -> set of WebSockets
        self.rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms[room_id].add(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.rooms[room_id].discard(websocket)
        if not self.rooms[room_id]:
            del self.rooms[room_id]  # Cleanup empty rooms

    async def broadcast_to_room(self, room_id: str, message: str, exclude: WebSocket | None = None):
        for ws in self.rooms[room_id]:
            if ws != exclude:
                await ws.send_text(message)
```

### Scaling with Redis Pub/Sub
```python
# Each WebSocket server subscribes to Redis channel
# When message published to Redis, all instances receive it and relay to local clients

async def redis_listener(channel: str):
    async for message in redis.subscribe(channel):
        await manager.broadcast_to_room(channel, message)
```

**Production Libraries:**
- `fastapi-websocket-pubsub` — fast pub/sub over WebSockets
- `encode/broadcaster` — Redis/PostgreSQL/Kafka backends

---

## 3. Heartbeat/Ping-Pong for Connection Health

### Application-Level Heartbeat
```python
async def heartbeat_task(websocket: WebSocket, interval: int = 30):
    """Send periodic pings to keep connection alive"""
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_text('{"type":"ping"}')
            # Client should respond with pong within timeout
    except WebSocketDisconnect:
        pass

# In endpoint:
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    heartbeat = asyncio.create_task(heartbeat_task(websocket))
    try:
        # ... receive loop
    finally:
        heartbeat.cancel()
        manager.disconnect(websocket)
```

### Uvicorn Built-in Ping
```python
# Command-line
uvicorn main:app --ws-ping-interval 300 --ws-ping-timeout 300

# Or in code
uvicorn.run("main:app", ws_ping_interval=300, ws_ping_timeout=300)
```

**Guidelines:**
- Heartbeat interval MUST be shorter than network device/firewall timeouts
- Handles NAT timeouts, mobile network transitions, silent disconnects
- Application-level gives more control/visibility than protocol-level

---

## 4. Broadcasting Market Data Efficiently

### Producer-Consumer with asyncio.Queue
```python
# Global queue for market data
market_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

# Producer (background task from SSI stream)
async def market_data_producer():
    async for tick in ssi_stream:
        try:
            market_queue.put_nowait(tick)  # Drop if full (backpressure)
        except asyncio.QueueFull:
            pass  # Or log dropped ticks

# Consumer (broadcasts to WebSocket clients)
async def broadcast_consumer():
    while True:
        tick = await market_queue.get()
        await manager.broadcast(json.dumps(tick))
```

### Per-Client Queues (High Traffic)
```python
class ConnectionManager:
    def __init__(self):
        self.clients: dict[WebSocket, asyncio.Queue] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.clients[websocket] = asyncio.Queue(maxsize=50)
        asyncio.create_task(self._send_loop(websocket))

    async def _send_loop(self, websocket: WebSocket):
        queue = self.clients[websocket]
        try:
            while True:
                msg = await queue.get()
                await websocket.send_text(msg)
        except WebSocketDisconnect:
            del self.clients[websocket]

    async def broadcast(self, message: str):
        for ws, queue in self.clients.items():
            try:
                queue.put_nowait(message)  # Drop if slow client
            except asyncio.QueueFull:
                pass  # Or disconnect slow client
```

**Backpressure Handling:**
- Fast producers can overwhelm slow consumers
- Per-client queue with `maxsize` prevents memory exhaustion
- Drop old messages or disconnect slow clients

**Distributed Architecture:**
- Central broker (Redis/NATS/Kafka) receives events
- Apply routing/filtering rules
- Fan out to topic-oriented channels
- Each WebSocket writer listens to relevant topics

---

## 5. Integration with Background Tasks (asyncio)

### Lifespan Context (FastAPI 0.93+)
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    producer_task = asyncio.create_task(market_data_producer())
    consumer_task = asyncio.create_task(broadcast_consumer())
    yield
    # Shutdown
    producer_task.cancel()
    consumer_task.cancel()
    await asyncio.gather(producer_task, consumer_task, return_exceptions=True)

app = FastAPI(lifespan=lifespan)
```

### Important Notes
- WebSocket routes **DO NOT** support `BackgroundTasks` (HTTP-only feature)
- Use `asyncio.create_task()` for concurrent operations in WebSocket handlers
- Tasks MUST be cancelled in `finally` block or lifespan shutdown

---

## 6. Starlette WebSocket Lifecycle

### Full Lifecycle Pattern
```python
from starlette.websockets import WebSocket, WebSocketDisconnect

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    # 1. Accept connection
    await manager.connect(room_id, websocket)

    # 2. Spawn background tasks for this connection
    heartbeat = asyncio.create_task(heartbeat_task(websocket))

    try:
        # 3. Receive loop
        while True:
            data = await websocket.receive_text()
            # Process client messages

    except WebSocketDisconnect:
        # 4. Client disconnected
        pass
    except Exception as e:
        # 5. Handle other errors
        logger.error(f"WebSocket error: {e}")
    finally:
        # 6. Cleanup ALWAYS runs
        heartbeat.cancel()
        manager.disconnect(room_id, websocket)
```

### Connection States
- `await websocket.accept()` — handshake complete
- `await websocket.receive_text()` — raises `WebSocketDisconnect` on close
- `await websocket.send_text()` — may raise if connection dead

---

## 7. Error Handling & Graceful Disconnection

### Exception Handling Best Practices
```python
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    tasks = []

    try:
        # Create background tasks
        tasks.append(asyncio.create_task(heartbeat_task(websocket)))
        tasks.append(asyncio.create_task(send_loop(websocket)))

        # Receive loop
        while True:
            msg = await websocket.receive_text()
            # Handle message

    except WebSocketDisconnect as e:
        logger.info(f"Client disconnected: code={e.code}, reason={e.reason}")
    except asyncio.CancelledError:
        logger.info("WebSocket task cancelled")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket.close(code=1011)  # Internal error
    finally:
        # Cancel all tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        # Remove from manager
        manager.disconnect(websocket)
```

### Connection Cleanup
```python
def disconnect(self, websocket: WebSocket):
    try:
        self.active_connections.remove(websocket)
    except ValueError:
        pass  # Already removed
```

**Critical:**
- ALWAYS use `finally` block for cleanup
- If connection not removed, broadcast loop sends to closed sockets → errors/slowdown
- Catch `WebSocketDisconnect` explicitly (raised by `receive_*()` methods)

### Graceful Shutdown Challenges
- Starlette/Uvicorn SIGTERM closes WebSockets abruptly (not graceful like HTTP)
- Shutdown handlers execute after tasks complete (infinite loops block)
- **Workaround:** Use shared `asyncio.Event()` checked in WebSocket loop, set on shutdown

---

## Recommended Architecture for Stock Tracker

```python
# 1. Room-based manager with subscription topics
class SubscriptionManager:
    def __init__(self):
        self.subscriptions: dict[str, set[WebSocket]] = defaultdict(set)
        self.client_queues: dict[WebSocket, asyncio.Queue] = {}

    async def subscribe(self, topic: str, websocket: WebSocket):
        await websocket.accept()
        self.subscriptions[topic].add(websocket)
        self.client_queues[websocket] = asyncio.Queue(maxsize=50)
        asyncio.create_task(self._send_loop(websocket))

    async def unsubscribe(self, topic: str, websocket: WebSocket):
        self.subscriptions[topic].discard(websocket)
        if websocket in self.client_queues:
            del self.client_queues[websocket]

    async def _send_loop(self, websocket: WebSocket):
        queue = self.client_queues[websocket]
        try:
            while True:
                msg = await asyncio.wait_for(queue.get(), timeout=60)
                await websocket.send_json(msg)
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass

    async def publish(self, topic: str, data: dict):
        """Called by SSI data producer"""
        for ws in self.subscriptions[topic]:
            queue = self.client_queues.get(ws)
            if queue:
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass  # Drop for slow clients

# 2. Lifespan integration
@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = app.state.subscription_manager
    ssi_task = asyncio.create_task(ssi_stream_handler(manager))
    yield
    ssi_task.cancel()
    await asyncio.gather(ssi_task, return_exceptions=True)

# 3. WebSocket endpoint with subscription
@app.websocket("/ws/market")
async def market_stream(websocket: WebSocket, symbols: str = "VN30"):
    manager = app.state.subscription_manager
    await manager.subscribe(symbols, websocket)
    heartbeat = asyncio.create_task(heartbeat_task(websocket))

    try:
        while True:
            # Can receive client commands (subscribe to more symbols, etc.)
            msg = await websocket.receive_json()
            if msg["action"] == "subscribe":
                await manager.subscribe(msg["topic"], websocket)
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat.cancel()
        await manager.unsubscribe(symbols, websocket)
```

---

## Key Takeaways

1. **ConnectionManager** is standard pattern — dict of rooms → sets of WebSockets
2. **Per-client queues** (asyncio.Queue) handle backpressure, prevent slow clients from blocking broadcast
3. **Application-level heartbeat** more flexible than Uvicorn ping — use background task per connection
4. **Lifespan context** manages global producer/consumer tasks
5. **ALWAYS cleanup** in `finally` block — cancel tasks, remove from manager
6. **WebSocketDisconnect** exception signals client close — catch explicitly
7. **Single-process** in-memory OK for prototype; Redis pub/sub for production multi-instance
8. **No BackgroundTasks** in WebSocket routes — use `asyncio.create_task()` instead

---

## Sources

- [WebSockets - FastAPI](https://fastapi.tiangolo.com/advanced/websockets/)
- [Broadcasting WebSocket messages with FastAPI](https://github.com/fastapi/fastapi/issues/4783)
- [Getting Started with FastAPI WebSockets | Better Stack](https://betterstack.com/community/guides/scaling-python/fastapi-websockets/)
- [Building Real-Time Applications with FastAPI WebSockets (2025)](https://dev-faizan.medium.com/building-real-time-applications-with-fastapi-websockets-a-complete-guide-2025-40f29d327733)
- [Realtime channels with FastAPI + Broadcaster](https://dev.to/sangarshanan/realtime-channels-with-fastapi-broadcaster-47jh)
- [fastapi-websocket-pubsub](https://github.com/permitio/fastapi_websocket_pubsub)
- [Scaling WebSockets with PUB/SUB using Python, Redis & FastAPI](https://medium.com/@nandagopal05/scaling-websockets-with-pub-sub-using-python-redis-fastapi-b16392ffe291)
- [How to Implement Heartbeat/Ping-Pong in WebSockets](https://oneuptime.com/blog/post/2026-01-27-websocket-heartbeat/view)
- [FastAPI WebSocket heartbeat discussion](https://github.com/fastapi/fastapi/discussions/8280)
- [WebSockets - Starlette](https://www.starlette.io/websockets/)
- [FastAPI/Starlette Lifecycle Guide](https://medium.com/@dynamicy/fastapi-starlette-lifecycle-guide-startup-order-pitfalls-best-practices-and-a-production-ready-53e29dcb9249)
- [FastAPI WebSocket producer-consumer demo](https://github.com/greed2411/fastapi_ws_producer_consumer)
- [How to Handle Large Scale WebSocket Traffic with FastAPI](https://hexshift.medium.com/how-to-handle-large-scale-websocket-traffic-with-fastapi-9c841f937f39)
- [Starlette WebSocket disconnect handling](https://github.com/Kludex/starlette/issues/759)
- [Graceful WebSocket shutdown issues](https://github.com/Kludex/uvicorn/discussions/2552)

---

## Unresolved Questions

None — research complete for stated scope.
