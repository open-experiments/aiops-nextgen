"""Tests for API Gateway service."""

import pytest

from app.api.proxy import get_backend_for_path, ROUTE_MAP


class TestRouteMapping:
    """Tests for route mapping."""

    def test_cluster_routes(self):
        assert get_backend_for_path("/api/v1/clusters") == "cluster-registry"
        assert get_backend_for_path("/api/v1/clusters/abc") == "cluster-registry"
        assert get_backend_for_path("/api/v1/fleet/summary") == "cluster-registry"

    def test_observability_routes(self):
        assert get_backend_for_path("/api/v1/metrics/query") == "observability-collector"
        assert get_backend_for_path("/api/v1/alerts") == "observability-collector"
        assert get_backend_for_path("/api/v1/gpu/nodes") == "observability-collector"

    def test_intelligence_routes(self):
        assert get_backend_for_path("/api/v1/chat/sessions") == "intelligence-engine"
        assert get_backend_for_path("/api/v1/personas") == "intelligence-engine"
        assert get_backend_for_path("/api/v1/analysis/anomaly") == "intelligence-engine"

    def test_streaming_routes(self):
        assert get_backend_for_path("/api/v1/streaming/status") == "realtime-streaming"

    def test_unknown_route(self):
        assert get_backend_for_path("/api/v1/unknown") is None
        assert get_backend_for_path("/other/path") is None


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    def test_normalize_path(self):
        from app.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=None)

        # UUIDs should be normalized
        path = "/api/v1/clusters/550e8400-e29b-41d4-a716-446655440000"
        normalized = middleware._normalize_path(path)
        assert "*" in normalized

        # Non-UUID paths should remain
        path = "/api/v1/clusters"
        normalized = middleware._normalize_path(path)
        assert "*" not in normalized

    def test_get_limit_config_default(self):
        from app.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=None)

        config = middleware._get_limit_config("/api/v1/clusters")
        assert config["limit"] == 300

    def test_get_limit_config_specific(self):
        from app.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=None)

        config = middleware._get_limit_config("/api/v1/metrics/query")
        assert config["limit"] == 60

        config = middleware._get_limit_config("/api/v1/chat/sessions")
        assert config["limit"] == 30
