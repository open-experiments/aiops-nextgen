"""Configuration management module.

Spec Reference: specs/09-deployment.md Section 8 - Configuration Management

This module provides:
- Environment-based configuration with validation
- Service-specific settings classes
- Cached settings access via get_settings()
"""

from .settings import (
    APIGatewaySettings,
    ClusterRegistrySettings,
    DatabaseSettings,
    Environment,
    IntelligenceEngineSettings,
    LLMProvider,
    LLMSettings,
    LogFormat,
    LogLevel,
    OAuthSettings,
    ObservabilityCollectorSettings,
    ObservabilitySettings,
    RealtimeStreamingSettings,
    RedisSettings,
    ServiceURLSettings,
    Settings,
    get_settings,
)

__all__ = [
    # Main settings
    "Settings",
    "get_settings",
    # Enums
    "Environment",
    "LogLevel",
    "LogFormat",
    "LLMProvider",
    # Component settings
    "DatabaseSettings",
    "RedisSettings",
    "LLMSettings",
    "ServiceURLSettings",
    "OAuthSettings",
    "ObservabilitySettings",
    # Service-specific settings
    "ClusterRegistrySettings",
    "ObservabilityCollectorSettings",
    "IntelligenceEngineSettings",
    "RealtimeStreamingSettings",
    "APIGatewaySettings",
]
