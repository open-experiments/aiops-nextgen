"""Tests for WebSocket authentication."""

import time
from unittest.mock import MagicMock, patch

import pytest
from app.middleware.ws_auth import WebSocketAuthenticator, WSTokenPayload
from fastapi import WebSocketException


@pytest.fixture
def ws_authenticator():
    return WebSocketAuthenticator()


@pytest.fixture
def mock_websocket():
    ws = MagicMock()
    ws.scope = {"query_string": b""}
    ws.headers = {}
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    return ws


class TestTokenExtraction:
    def test_extract_token_from_query_param(self, ws_authenticator, mock_websocket):
        """Test token extraction from query parameter."""
        mock_websocket.scope = {"query_string": b"token=my-jwt-token"}

        token = ws_authenticator.extract_token(mock_websocket)

        assert token == "my-jwt-token"

    def test_extract_token_from_protocol_header(self, ws_authenticator, mock_websocket):
        """Test token extraction from Sec-WebSocket-Protocol header."""
        mock_websocket.headers = {"sec-websocket-protocol": "bearer, my-jwt-token"}

        token = ws_authenticator.extract_token(mock_websocket)

        assert token == "my-jwt-token"

    def test_extract_token_query_param_priority(self, ws_authenticator, mock_websocket):
        """Test query parameter takes priority over header."""
        mock_websocket.scope = {"query_string": b"token=query-token"}
        mock_websocket.headers = {"sec-websocket-protocol": "bearer, header-token"}

        token = ws_authenticator.extract_token(mock_websocket)

        assert token == "query-token"

    def test_extract_token_missing(self, ws_authenticator, mock_websocket):
        """Test None returned when no token present."""
        token = ws_authenticator.extract_token(mock_websocket)

        assert token is None

    def test_extract_token_empty_query_string(self, ws_authenticator, mock_websocket):
        """Test empty query string returns None."""
        mock_websocket.scope = {"query_string": b""}

        token = ws_authenticator.extract_token(mock_websocket)

        assert token is None

    def test_extract_token_invalid_protocol_header(self, ws_authenticator, mock_websocket):
        """Test invalid protocol header format returns None."""
        mock_websocket.headers = {"sec-websocket-protocol": "invalid-format"}

        token = ws_authenticator.extract_token(mock_websocket)

        assert token is None


class TestAuthentication:
    async def test_authenticate_missing_token(self, ws_authenticator, mock_websocket):
        """Test authentication fails without token."""
        with pytest.raises(WebSocketException) as exc_info:
            await ws_authenticator.authenticate(mock_websocket)

        assert exc_info.value.code == 1008
        assert "Authentication required" in exc_info.value.reason

    async def test_authenticate_invalid_token(self, ws_authenticator, mock_websocket):
        """Test authentication fails with invalid token."""
        mock_websocket.scope = {"query_string": b"token=invalid-token"}

        with patch.object(ws_authenticator, "get_jwks", return_value={"keys": []}):
            with pytest.raises(WebSocketException) as exc_info:
                await ws_authenticator.authenticate(mock_websocket)

            assert exc_info.value.code == 1008


class TestWSTokenPayload:
    def test_payload_validation(self):
        """Test token payload model validation."""
        payload = WSTokenPayload(
            sub="user-123",
            preferred_username="testuser",
            groups=["admins"],
            exp=int(time.time()) + 3600,
        )

        assert payload.sub == "user-123"
        assert payload.groups == ["admins"]

    def test_payload_default_groups(self):
        """Test empty groups default."""
        payload = WSTokenPayload(
            sub="user-123",
            preferred_username="testuser",
            exp=int(time.time()) + 3600,
        )

        assert payload.groups == []

    def test_payload_with_all_fields(self):
        """Test payload with all fields populated."""
        exp_time = int(time.time()) + 3600
        payload = WSTokenPayload(
            sub="user-456",
            preferred_username="admin",
            groups=["cluster-admins", "developers"],
            exp=exp_time,
        )

        assert payload.sub == "user-456"
        assert payload.preferred_username == "admin"
        assert len(payload.groups) == 2
        assert payload.exp == exp_time
