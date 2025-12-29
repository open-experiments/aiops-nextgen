"""Tests for OAuth middleware."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.middleware.oauth import OAuthMiddleware, TokenPayload
from fastapi import HTTPException


@pytest.fixture
def oauth_middleware():
    return OAuthMiddleware()


@pytest.fixture
def valid_token_payload():
    return {
        "sub": "user-123",
        "preferred_username": "testuser",
        "email": "test@example.com",
        "groups": ["cluster-admins"],
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "iss": "https://oauth.openshift.local",
    }


@pytest.fixture
def mock_jwks():
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-1",
                "use": "sig",
                "n": "test-n-value",
                "e": "AQAB",
            }
        ]
    }


class TestOAuthMiddleware:
    async def test_get_oauth_config_success(self, oauth_middleware):
        """Test fetching OAuth configuration."""
        mock_config = {
            "issuer": "https://oauth.openshift.local",
            "authorization_endpoint": "https://oauth.openshift.local/authorize",
            "token_endpoint": "https://oauth.openshift.local/token",
            "userinfo_endpoint": "https://oauth.openshift.local/userinfo",
            "jwks_uri": "https://oauth.openshift.local/.well-known/jwks.json",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_config
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            config = await oauth_middleware.get_oauth_config()

            assert config.issuer == mock_config["issuer"]
            assert config.jwks_uri == mock_config["jwks_uri"]

    async def test_get_oauth_config_failure(self, oauth_middleware):
        """Test OAuth config fetch failure."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(HTTPException) as exc_info:
                await oauth_middleware.get_oauth_config()

            assert exc_info.value.status_code == 503

    async def test_validate_token_expired(self, oauth_middleware, valid_token_payload):
        """Test expired token rejection."""
        valid_token_payload["exp"] = int(time.time()) - 3600  # Expired

        with pytest.raises(HTTPException) as exc_info:
            await oauth_middleware.validate_token("expired-token")

        assert exc_info.value.status_code == 401

    async def test_health_endpoint_bypass(self, oauth_middleware):
        """Test health endpoints bypass authentication."""
        mock_request = MagicMock()
        mock_request.url.path = "/health"

        result = await oauth_middleware(mock_request)

        assert result is None

    async def test_ready_endpoint_bypass(self, oauth_middleware):
        """Test ready endpoints bypass authentication."""
        mock_request = MagicMock()
        mock_request.url.path = "/ready"

        result = await oauth_middleware(mock_request)

        assert result is None

    async def test_metrics_endpoint_bypass(self, oauth_middleware):
        """Test metrics endpoints bypass authentication."""
        mock_request = MagicMock()
        mock_request.url.path = "/metrics"

        result = await oauth_middleware(mock_request)

        assert result is None


class TestTokenPayload:
    def test_token_payload_validation(self, valid_token_payload):
        """Test token payload model validation."""
        payload = TokenPayload(**valid_token_payload)

        assert payload.sub == "user-123"
        assert payload.preferred_username == "testuser"
        assert "cluster-admins" in payload.groups

    def test_token_payload_optional_fields(self):
        """Test token payload with optional fields missing."""
        minimal_payload = {
            "sub": "user-123",
            "preferred_username": "testuser",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "iss": "https://oauth.openshift.local",
        }

        payload = TokenPayload(**minimal_payload)

        assert payload.email is None
        assert payload.groups == []
