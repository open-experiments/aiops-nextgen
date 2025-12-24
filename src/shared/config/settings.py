"""Configuration management with Pydantic Settings.

Spec References:
- specs/09-deployment.md Section 8 - Configuration Management
- specs/00-overview.md Section 2.1 - Air-Gapped Ready design
- specs/04-intelligence-engine.md - LLM configuration

Environment variables are loaded from:
1. Environment variables (highest priority)
2. .env file (development)
3. Defaults (lowest priority)
"""

from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging level."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Logging format."""

    JSON = "json"
    TEXT = "text"


class LLMProvider(str, Enum):
    """LLM provider type.

    Spec Reference: specs/00-overview.md Section 2.1
    - Local vLLM is primary/preferred
    - External APIs are optional for connected environments
    """

    LOCAL = "local"  # vLLM - preferred for air-gapped
    OPENAI = "openai"  # OpenAI API compatible (external)
    ANTHROPIC = "anthropic"  # Claude API (external, optional)


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration.

    Spec Reference: specs/09-deployment.md Section 8.2
    """

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    user: str = Field(default="aiops", description="Database user")
    password: str = Field(default="", description="Database password")
    database: str = Field(default="aiops", description="Database name")

    @property
    def url(self) -> str:
        """Build database URL (sync driver)."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_url(self) -> str:
        """Build async database URL (asyncpg driver)."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseSettings):
    """Redis configuration.

    Spec Reference: specs/08-integration-matrix.md Section 6.2
    """

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: str | None = Field(default=None, description="Redis password")

    @property
    def url(self) -> str:
        """Build Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}"
        return f"redis://{self.host}:{self.port}"


class LLMSettings(BaseSettings):
    """LLM configuration.

    Spec Reference:
    - specs/00-overview.md Section 2.1 - Air-Gapped Ready
    - specs/04-intelligence-engine.md Section 2.1 - LLM Router
    """

    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: LLMProvider = Field(
        default=LLMProvider.LOCAL,
        description="LLM provider (local vLLM preferred)",
    )

    # Local vLLM settings (primary/preferred)
    local_url: str = Field(
        default="http://localhost:8080/v1",
        description="Local vLLM server URL",
    )
    local_model: str = Field(
        default="meta-llama/Llama-3.2-3B-Instruct",
        description="Local model name",
    )

    # External API settings (optional, for connected environments)
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model")

    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514", description="Anthropic model"
    )

    # Common settings
    max_tokens: int = Field(default=4096, description="Max tokens for completion")
    temperature: float = Field(default=0.7, description="Temperature for sampling")
    timeout_seconds: int = Field(default=120, description="Request timeout")


class ServiceURLSettings(BaseSettings):
    """Internal service URLs.

    Spec Reference: specs/08-integration-matrix.md Section 4
    """

    model_config = SettingsConfigDict(env_prefix="SERVICE_")

    cluster_registry_url: str = Field(
        default="http://cluster-registry:8080",
        description="Cluster Registry service URL",
    )
    observability_collector_url: str = Field(
        default="http://observability-collector:8080",
        description="Observability Collector service URL",
    )
    intelligence_engine_url: str = Field(
        default="http://intelligence-engine:8080",
        description="Intelligence Engine service URL",
    )
    realtime_streaming_url: str = Field(
        default="http://realtime-streaming:8080",
        description="Realtime Streaming service URL",
    )


class OAuthSettings(BaseSettings):
    """OAuth configuration.

    Spec Reference: specs/09-deployment.md Section 8.2
    """

    model_config = SettingsConfigDict(env_prefix="OAUTH_")

    issuer: str = Field(default="", description="OAuth issuer URL")
    client_id: str = Field(default="aiops-nextgen", description="OAuth client ID")
    client_secret: str = Field(default="", description="OAuth client secret")


class ObservabilitySettings(BaseSettings):
    """Observability configuration.

    Spec Reference: specs/09-deployment.md Section 8.1
    """

    model_config = SettingsConfigDict(env_prefix="")

    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    tracing_enabled: bool = Field(default=True, description="Enable OpenTelemetry tracing")
    otel_exporter_endpoint: str = Field(
        default="http://otel-collector:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
        description="OpenTelemetry collector endpoint",
    )


class Settings(BaseSettings):
    """Main application settings.

    Spec Reference: specs/09-deployment.md Section 8

    All settings can be overridden via environment variables.
    For nested settings, use the appropriate prefix (e.g., POSTGRES_HOST).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application metadata
    app_name: str = Field(default="aiops-nextgen", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        alias="ENV",
        description="Deployment environment",
    )

    # Logging configuration
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_format: LogFormat = Field(default=LogFormat.JSON, description="Logging format")

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8080, description="Server bind port")
    workers: int = Field(default=1, description="Number of worker processes")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    services: ServiceURLSettings = Field(default_factory=ServiceURLSettings)
    oauth: OAuthSettings = Field(default_factory=OAuthSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    @field_validator("workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        """Ensure workers is at least 1."""
        return max(1, v)

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses LRU cache to avoid re-parsing environment variables.
    """
    return Settings()


# Service-specific settings classes for fine-grained control


class ClusterRegistrySettings(Settings):
    """Settings specific to Cluster Registry service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Cluster Registry specific settings
    health_check_interval_seconds: int = Field(
        default=30,
        description="Interval between cluster health checks",
    )
    credential_cache_ttl_seconds: int = Field(
        default=300,
        description="TTL for cached credentials",
    )


class ObservabilityCollectorSettings(Settings):
    """Settings specific to Observability Collector service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Observability Collector specific settings
    metrics_cache_ttl_seconds: int = Field(
        default=30,
        description="TTL for cached metrics queries",
    )
    max_concurrent_cluster_queries: int = Field(
        default=10,
        description="Max concurrent queries to clusters",
    )


class IntelligenceEngineSettings(Settings):
    """Settings specific to Intelligence Engine service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Intelligence Engine specific settings
    chat_session_ttl_hours: int = Field(
        default=24,
        description="Default chat session TTL in hours",
    )
    max_context_messages: int = Field(
        default=50,
        description="Maximum messages to include in context",
    )


class RealtimeStreamingSettings(Settings):
    """Settings specific to Realtime Streaming service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Realtime Streaming specific settings
    websocket_heartbeat_seconds: int = Field(
        default=30,
        description="WebSocket heartbeat interval",
    )
    max_subscriptions_per_client: int = Field(
        default=100,
        description="Maximum subscriptions per WebSocket client",
    )


class APIGatewaySettings(Settings):
    """Settings specific to API Gateway service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Gateway specific settings
    rate_limit_requests: int = Field(
        default=100,
        description="Rate limit requests per window",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        description="Rate limit window in seconds",
    )
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed origins",
    )
