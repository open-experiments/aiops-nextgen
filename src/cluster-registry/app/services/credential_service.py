"""Credential service for secure credential management.

Spec Reference: specs/02-cluster-registry.md Section 5.2

Note: For local development, credentials are stored in memory.
In production, credentials are stored in Kubernetes Secrets.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from shared.observability import get_logger
from shared.redis_client import RedisClient

from ..schemas.credentials import (
    CredentialInput,
    CredentialStatus,
    EndpointValidation,
    ValidationResult,
    ValidationStatus,
)
from .event_service import EventService

logger = get_logger(__name__)


# In-memory credential store for local development
# In production, this would use Kubernetes Secrets
_credential_store: dict[str, dict[str, Any]] = {}


class CredentialService:
    """Service for secure credential management.

    Spec Reference: specs/02-cluster-registry.md Section 5.2

    In local development mode, credentials are stored in memory.
    In production, credentials are stored in Kubernetes Secrets
    (spec section 7.2).
    """

    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.event_service = EventService(redis_client)

    async def store(self, cluster_id: UUID, credentials: CredentialInput) -> CredentialStatus:
        """Store credentials securely.

        Spec Reference: specs/02-cluster-registry.md Section 5.2

        In local development: stores in memory
        In production: stores in Kubernetes Secret
        """
        # Validate credentials (mock validation for local dev)
        validation = await self._validate_credentials(cluster_id, credentials)

        # Store credentials (in-memory for local dev)
        _credential_store[str(cluster_id)] = {
            "auth_type": credentials.auth_type.value,
            "kubeconfig": credentials.kubeconfig,
            "token": credentials.token,
            "prometheus_token": credentials.prometheus_token,
            "tempo_token": credentials.tempo_token,
            "loki_token": credentials.loki_token,
            "stored_at": datetime.utcnow().isoformat(),
        }

        logger.info("Credentials stored", cluster_id=str(cluster_id))

        # Publish event
        await self.event_service.publish_cluster_credentials_updated(cluster_id)

        # Set expiry (30 days by default)
        expires_at = datetime.utcnow() + timedelta(days=30)

        return CredentialStatus(
            status="stored",
            validation=validation,
            expires_at=expires_at,
        )

    async def validate(self, cluster_id: UUID) -> ValidationResult:
        """Validate stored credentials.

        Spec Reference: specs/02-cluster-registry.md Section 5.2
        """
        creds = _credential_store.get(str(cluster_id))
        if not creds:
            return ValidationResult(
                api_server=EndpointValidation(
                    status=ValidationStatus.FAILED,
                    error="No credentials stored",
                )
            )

        # Mock validation - in production, this would actually test connectivity
        return ValidationResult(
            api_server=EndpointValidation(status=ValidationStatus.SUCCESS),
            prometheus=EndpointValidation(status=ValidationStatus.SUCCESS)
            if creds.get("prometheus_token")
            else None,
            tempo=EndpointValidation(status=ValidationStatus.SUCCESS)
            if creds.get("tempo_token")
            else None,
            loki=EndpointValidation(status=ValidationStatus.SUCCESS)
            if creds.get("loki_token")
            else None,
        )

    async def rotate(self, cluster_id: UUID, new_credentials: CredentialInput) -> CredentialStatus:
        """Rotate credentials with zero-downtime.

        Spec Reference: specs/02-cluster-registry.md Section 5.2
        """
        # Validate new credentials first
        validation = await self._validate_credentials(cluster_id, new_credentials)

        if validation.api_server.status == ValidationStatus.FAILED:
            raise ValueError("New credentials failed validation")

        # Store new credentials
        return await self.store(cluster_id, new_credentials)

    async def get_for_use(self, cluster_id: UUID) -> dict[str, Any] | None:
        """Get decrypted credentials for internal use.

        Spec Reference: specs/02-cluster-registry.md Section 5.2

        WARNING: This should only be called by internal services.
        Never expose credentials in API responses.
        """
        return _credential_store.get(str(cluster_id))

    async def delete(self, cluster_id: UUID) -> bool:
        """Delete stored credentials.

        Spec Reference: specs/02-cluster-registry.md Section 5.2
        """
        if str(cluster_id) in _credential_store:
            del _credential_store[str(cluster_id)]
            logger.info("Credentials deleted", cluster_id=str(cluster_id))
            return True
        return False

    async def _validate_credentials(
        self, cluster_id: UUID, credentials: CredentialInput
    ) -> ValidationResult:
        """Validate credentials against endpoints.

        In local development, this is mocked.
        In production, this would actually test connectivity.
        """
        # Mock validation - always succeeds in local dev
        api_validation = EndpointValidation(status=ValidationStatus.SUCCESS)

        prometheus_validation = None
        if credentials.prometheus_token:
            prometheus_validation = EndpointValidation(status=ValidationStatus.SUCCESS)

        tempo_validation = None
        if credentials.tempo_token:
            tempo_validation = EndpointValidation(status=ValidationStatus.SUCCESS)

        loki_validation = None
        if credentials.loki_token:
            loki_validation = EndpointValidation(status=ValidationStatus.SUCCESS)

        return ValidationResult(
            api_server=api_validation,
            prometheus=prometheus_validation,
            tempo=tempo_validation,
            loki=loki_validation,
        )
