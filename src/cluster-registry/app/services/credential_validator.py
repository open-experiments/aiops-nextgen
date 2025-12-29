"""Cluster Credential Validation Service.

Spec Reference: specs/02-cluster-registry.md Section 3.3

Validates credentials by making actual API calls to the target cluster.
"""

import base64
from enum import Enum

import httpx
from pydantic import BaseModel

from shared.models import AuthType, ClusterCredentials
from shared.observability import get_logger

logger = get_logger(__name__)


class ValidationStatus(str, Enum):
    """Credential validation status."""

    VALID = "valid"
    INVALID = "invalid"
    UNREACHABLE = "unreachable"
    EXPIRED = "expired"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"


class ValidationResult(BaseModel):
    """Result of credential validation."""

    status: ValidationStatus
    message: str
    api_version: str | None = None
    username: str | None = None
    groups: list[str] | None = None


class CredentialValidator:
    """Validates cluster credentials against actual cluster APIs."""

    def __init__(self):
        self.timeout = 10.0  # seconds

    async def validate(
        self,
        api_url: str,
        credentials: ClusterCredentials,
    ) -> ValidationResult:
        """Validate credentials against cluster API.

        Args:
            api_url: Kubernetes/OpenShift API URL
            credentials: Credentials to validate

        Returns:
            ValidationResult with status and details
        """
        try:
            # Build authentication headers
            headers = self._build_auth_headers(credentials)

            # Verify SSL based on credentials setting
            verify_ssl = not credentials.skip_tls_verify

            async with httpx.AsyncClient(
                verify=verify_ssl,
                timeout=self.timeout,
                cert=self._get_client_cert(credentials),
            ) as client:
                # Test API access with version endpoint
                version_result = await self._check_api_version(client, api_url, headers)

                if version_result.status != ValidationStatus.VALID:
                    return version_result

                # Verify user identity
                user_result = await self._check_user_identity(client, api_url, headers)

                return user_result

        except httpx.ConnectError as e:
            logger.warning("Cluster unreachable", api_url=api_url, error=str(e))
            return ValidationResult(
                status=ValidationStatus.UNREACHABLE,
                message=f"Cannot connect to cluster: {e!s}",
            )

        except httpx.TimeoutException:
            logger.warning("Cluster connection timeout", api_url=api_url)
            return ValidationResult(
                status=ValidationStatus.UNREACHABLE,
                message="Connection timeout",
            )

        except Exception as e:
            logger.error("Validation error", api_url=api_url, error=str(e))
            return ValidationResult(
                status=ValidationStatus.INVALID,
                message=f"Validation failed: {e!s}",
            )

    def _build_auth_headers(self, credentials: ClusterCredentials) -> dict[str, str]:
        """Build HTTP headers for authentication."""
        headers = {}

        if credentials.auth_type in (AuthType.TOKEN, AuthType.SERVICE_ACCOUNT):
            headers["Authorization"] = f"Bearer {credentials.token}"

        elif credentials.auth_type == AuthType.BASIC:
            auth_string = f"{credentials.username}:{credentials.password}"
            encoded = base64.b64encode(auth_string.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        return headers

    def _get_client_cert(
        self, credentials: ClusterCredentials
    ) -> tuple[str, str] | None:
        """Get client certificate tuple for mTLS."""
        if credentials.auth_type == AuthType.CERTIFICATE:
            # In production, certs would be written to temp files
            # For now, return None and handle in a future iteration
            return None
        return None

    async def _check_api_version(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> ValidationResult:
        """Check cluster API version endpoint."""
        version_url = f"{api_url.rstrip('/')}/version"

        response = await client.get(version_url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return ValidationResult(
                status=ValidationStatus.VALID,
                message="API accessible",
                api_version=data.get("gitVersion", "unknown"),
            )

        if response.status_code == 401:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                message="Authentication failed",
            )

        if response.status_code == 403:
            # 403 on version endpoint is unusual but possible
            return ValidationResult(
                status=ValidationStatus.INSUFFICIENT_PERMISSIONS,
                message="Access denied to version endpoint",
            )

        return ValidationResult(
            status=ValidationStatus.INVALID,
            message=f"Unexpected status code: {response.status_code}",
        )

    async def _check_user_identity(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> ValidationResult:
        """Check user identity via SelfSubjectReview."""
        # Use SelfSubjectAccessReview to verify identity
        review_url = f"{api_url.rstrip('/')}/apis/authentication.k8s.io/v1/selfsubjectreviews"

        review_body = {
            "apiVersion": "authentication.k8s.io/v1",
            "kind": "SelfSubjectReview",
            "status": {},
        }

        response = await client.post(
            review_url,
            headers={**headers, "Content-Type": "application/json"},
            json=review_body,
        )

        if response.status_code == 201:
            data = response.json()
            user_info = data.get("status", {}).get("userInfo", {})

            return ValidationResult(
                status=ValidationStatus.VALID,
                message="Credentials validated successfully",
                username=user_info.get("username"),
                groups=user_info.get("groups", []),
            )

        # Fall back to version check result if SelfSubjectReview not available
        if response.status_code == 404:
            return ValidationResult(
                status=ValidationStatus.VALID,
                message="Credentials valid (SelfSubjectReview not available)",
            )

        if response.status_code == 401:
            return ValidationResult(
                status=ValidationStatus.EXPIRED,
                message="Token expired or invalid",
            )

        return ValidationResult(
            status=ValidationStatus.INVALID,
            message=f"Identity check failed: {response.status_code}",
        )


# Singleton instance
credential_validator = CredentialValidator()


async def validate_cluster_credentials(
    api_url: str,
    credentials: ClusterCredentials,
) -> ValidationResult:
    """Validate cluster credentials."""
    return await credential_validator.validate(api_url, credentials)
