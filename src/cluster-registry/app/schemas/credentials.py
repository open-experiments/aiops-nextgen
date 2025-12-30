"""Credential request/response schemas.

Spec Reference: specs/02-cluster-registry.md Section 4.2, 5.2
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AuthType(str, Enum):
    """Authentication type for cluster access."""

    KUBECONFIG = "KUBECONFIG"
    TOKEN = "TOKEN"
    CERTIFICATE = "CERTIFICATE"


class CredentialInput(BaseModel):
    """Credential upload request.

    Spec Reference: specs/02-cluster-registry.md Section 4.2
    """

    auth_type: AuthType = Field(default=AuthType.KUBECONFIG, description="Authentication type")
    kubeconfig: str | None = Field(None, description="Base64-encoded kubeconfig")
    token: str | None = Field(None, description="Bearer token")
    certificate: str | None = Field(None, description="Client certificate (PEM)")
    key: str | None = Field(None, description="Client key (PEM)")
    prometheus_token: str | None = Field(None, description="Token for Prometheus access")
    tempo_token: str | None = Field(None, description="Token for Tempo access")
    loki_token: str | None = Field(None, description="Token for Loki access")


class ValidationStatus(str, Enum):
    """Validation result status."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class EndpointValidation(BaseModel):
    """Validation result for a single endpoint."""

    status: ValidationStatus
    error: str | None = None


class ValidationResult(BaseModel):
    """Credential validation result.

    Spec Reference: specs/02-cluster-registry.md Section 4.2
    """

    api_server: EndpointValidation
    prometheus: EndpointValidation | None = None
    tempo: EndpointValidation | None = None
    loki: EndpointValidation | None = None


class CredentialStatus(BaseModel):
    """Credential storage status response.

    Spec Reference: specs/02-cluster-registry.md Section 4.2
    """

    status: str = "stored"
    validation: ValidationResult
    expires_at: datetime | None = None
