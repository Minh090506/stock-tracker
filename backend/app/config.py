from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # SSI FastConnect
    ssi_consumer_id: str = ""
    ssi_consumer_secret: str = ""
    ssi_base_url: str = "https://fc-data.ssi.com.vn/"
    ssi_stream_url: str = "https://fc-data.ssi.com.vn/"

    # Database
    database_url: str = "postgresql://stock:stock@localhost:5432/stock_tracker"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # CORS — comma-separated origins
    cors_origins: str = "http://localhost:5173"

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Channel R (foreign investor) assumed update interval for speed calculation
    channel_r_interval_ms: int = 1000

    # Futures contract override (e.g., "VN30F2603" to force specific contract)
    futures_override: str = ""

    # WebSocket broadcast
    ws_broadcast_interval: float = 1.0    # seconds between broadcasts (legacy)
    ws_throttle_interval_ms: int = 500    # per-channel throttle for event-driven publisher
    ws_heartbeat_interval: float = 30.0   # seconds between ping frames
    ws_heartbeat_timeout: float = 10.0    # seconds to wait for pong
    ws_queue_size: int = 50               # per-client queue maxsize

    # WebSocket authentication & rate limiting
    ws_auth_token: str = ""               # token for WS auth (empty = disabled)
    ws_max_connections_per_ip: int = 5    # max concurrent WS connections per IP

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
