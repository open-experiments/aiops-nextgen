"""Tests for credential validation service."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.credential_validator import (
    CredentialValidator,
    ValidationResult,
    ValidationStatus,
)
from shared.models import AuthType, ClusterCredentials


@pytest.fixture
def validator():
    return CredentialValidator()


@pytest.fixture
def token_credentials():
    return ClusterCredentials(
        auth_type=AuthType.TOKEN,
        token="test-token-12345",
    )


@pytest.fixture
def basic_credentials():
    return ClusterCredentials(
        auth_type=AuthType.BASIC,
        username="admin",
        password="secret",
    )


class TestAuthHeaders:
    def test_token_auth_header(self, validator, token_credentials):
        """Test Bearer token header generation."""
        headers = validator._build_auth_headers(token_credentials)

        assert headers["Authorization"] == "Bearer test-token-12345"

    def test_basic_auth_header(self, validator, basic_credentials):
        """Test Basic auth header generation."""
        headers = validator._build_auth_headers(basic_credentials)

        expected = base64.b64encode(b"admin:secret").decode()
        assert headers["Authorization"] == f"Basic {expected}"


class TestValidation:
    async def test_valid_credentials(self, validator, token_credentials):
        """Test successful credential validation."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock version response
            version_response = MagicMock()
            version_response.status_code = 200
            version_response.json.return_value = {"gitVersion": "v1.28.0"}

            # Mock identity response
            identity_response = MagicMock()
            identity_response.status_code = 201
            identity_response.json.return_value = {
                "status": {
                    "userInfo": {
                        "username": "system:serviceaccount:default:aiops",
                        "groups": ["system:authenticated"],
                    }
                }
            }

            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=version_response)
            mock_instance.post = AsyncMock(return_value=identity_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await validator.validate(
                "https://api.cluster.local:6443",
                token_credentials,
            )

            assert result.status == ValidationStatus.VALID
            assert result.username == "system:serviceaccount:default:aiops"

    async def test_invalid_token(self, validator, token_credentials):
        """Test invalid token returns INVALID status."""
        with patch("httpx.AsyncClient") as mock_client:
            response = MagicMock()
            response.status_code = 401

            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await validator.validate(
                "https://api.cluster.local:6443",
                token_credentials,
            )

            assert result.status == ValidationStatus.INVALID

    async def test_unreachable_cluster(self, validator, token_credentials):
        """Test unreachable cluster returns UNREACHABLE status."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await validator.validate(
                "https://api.cluster.local:6443",
                token_credentials,
            )

            assert result.status == ValidationStatus.UNREACHABLE

    async def test_timeout(self, validator, token_credentials):
        """Test timeout returns UNREACHABLE status."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await validator.validate(
                "https://api.cluster.local:6443",
                token_credentials,
            )

            assert result.status == ValidationStatus.UNREACHABLE
            assert "timeout" in result.message.lower()


class TestValidationResult:
    def test_valid_result_model(self):
        """Test ValidationResult model."""
        result = ValidationResult(
            status=ValidationStatus.VALID,
            message="Success",
            api_version="v1.28.0",
            username="admin",
            groups=["admins", "developers"],
        )

        assert result.status == ValidationStatus.VALID
        assert len(result.groups) == 2
