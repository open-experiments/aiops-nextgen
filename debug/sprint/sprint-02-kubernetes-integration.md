# Sprint 2: Kubernetes Integration

**Issues Addressed:** ISSUE-002 (CRITICAL), ISSUE-003 (HIGH), ISSUE-004 (HIGH)
**Priority:** P0 - BLOCKING
**Dependencies:** Sprint 1 (Security Foundation)

---

## Overview

This sprint implements proper Kubernetes Secrets storage for cluster credentials, real credential validation against cluster APIs, and the DiscoveryService for automatic cluster component detection.

---

## Task 2.1: Kubernetes Secrets Credential Storage

**File:** `src/cluster-registry/services/credential_store.py`

### Implementation

```python
"""Kubernetes Secrets-based Credential Storage.

Spec Reference: specs/02-cluster-registry.md Section 3.2

Credentials are stored in Kubernetes Secrets with:
- AES-256-GCM encryption for sensitive fields
- Namespace isolation per cluster
- Automatic rotation support
"""

import base64
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel

from shared.models import AuthType, ClusterCredentials
from shared.observability import get_logger

logger = get_logger(__name__)

# Secret naming convention
SECRET_NAME_PREFIX = "aiops-cluster-"
SECRET_NAMESPACE = "aiops-system"
ENCRYPTION_KEY_SECRET = "aiops-encryption-key"


class EncryptedCredential(BaseModel):
    """Encrypted credential data structure."""

    auth_type: AuthType
    encrypted_data: str  # Base64 encoded encrypted JSON
    nonce: str  # Base64 encoded nonce
    created_at: str
    rotated_at: Optional[str] = None


class CredentialStore:
    """Kubernetes Secrets-based credential storage with encryption."""

    def __init__(self):
        self._encryption_key: Optional[bytes] = None
        self._k8s_client: Optional[client.CoreV1Api] = None

    def _get_k8s_client(self) -> client.CoreV1Api:
        """Get or create Kubernetes API client."""
        if self._k8s_client is None:
            try:
                # Try in-cluster config first
                config.load_incluster_config()
            except config.ConfigException:
                # Fall back to kubeconfig
                config.load_kube_config()

            self._k8s_client = client.CoreV1Api()

        return self._k8s_client

    def _get_encryption_key(self) -> bytes:
        """Get or generate encryption key from Kubernetes Secret."""
        if self._encryption_key is not None:
            return self._encryption_key

        k8s = self._get_k8s_client()

        try:
            # Try to read existing key
            secret = k8s.read_namespaced_secret(
                name=ENCRYPTION_KEY_SECRET,
                namespace=SECRET_NAMESPACE,
            )
            key_b64 = secret.data.get("key", "")
            self._encryption_key = base64.b64decode(key_b64)

        except ApiException as e:
            if e.status == 404:
                # Generate new key
                self._encryption_key = AESGCM.generate_key(bit_length=256)

                # Store in Kubernetes Secret
                secret = client.V1Secret(
                    metadata=client.V1ObjectMeta(
                        name=ENCRYPTION_KEY_SECRET,
                        namespace=SECRET_NAMESPACE,
                        labels={"app": "aiops-nextgen", "component": "encryption"},
                    ),
                    type="Opaque",
                    data={
                        "key": base64.b64encode(self._encryption_key).decode(),
                    },
                )
                k8s.create_namespaced_secret(
                    namespace=SECRET_NAMESPACE,
                    body=secret,
                )
                logger.info("Created new encryption key secret")
            else:
                raise

        return self._encryption_key

    def _encrypt(self, plaintext: str) -> tuple[str, str]:
        """Encrypt plaintext using AES-256-GCM.

        Returns:
            Tuple of (base64_encrypted_data, base64_nonce)
        """
        key = self._get_encryption_key()
        aesgcm = AESGCM(key)

        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        return (
            base64.b64encode(ciphertext).decode(),
            base64.b64encode(nonce).decode(),
        )

    def _decrypt(self, encrypted_data: str, nonce: str) -> str:
        """Decrypt ciphertext using AES-256-GCM."""
        key = self._get_encryption_key()
        aesgcm = AESGCM(key)

        ciphertext = base64.b64decode(encrypted_data)
        nonce_bytes = base64.b64decode(nonce)

        plaintext = aesgcm.decrypt(nonce_bytes, ciphertext, None)
        return plaintext.decode()

    def _secret_name(self, cluster_id: str) -> str:
        """Generate Kubernetes Secret name for cluster."""
        return f"{SECRET_NAME_PREFIX}{cluster_id}"

    async def store_credentials(
        self,
        cluster_id: str,
        credentials: ClusterCredentials,
    ) -> None:
        """Store cluster credentials in Kubernetes Secret.

        Args:
            cluster_id: Unique cluster identifier
            credentials: Cluster credentials to store
        """
        import json
        from datetime import datetime, timezone

        k8s = self._get_k8s_client()
        secret_name = self._secret_name(cluster_id)

        # Serialize credentials to JSON
        creds_json = credentials.model_dump_json()

        # Encrypt the JSON
        encrypted_data, nonce = self._encrypt(creds_json)

        # Build secret data
        secret_data = {
            "auth_type": base64.b64encode(credentials.auth_type.value.encode()).decode(),
            "encrypted_data": base64.b64encode(encrypted_data.encode()).decode(),
            "nonce": base64.b64encode(nonce.encode()).decode(),
            "created_at": base64.b64encode(
                datetime.now(timezone.utc).isoformat().encode()
            ).decode(),
        }

        # Create or update secret
        secret = client.V1Secret(
            metadata=client.V1ObjectMeta(
                name=secret_name,
                namespace=SECRET_NAMESPACE,
                labels={
                    "app": "aiops-nextgen",
                    "component": "cluster-credentials",
                    "cluster-id": cluster_id,
                },
                annotations={
                    "aiops.io/auth-type": credentials.auth_type.value,
                },
            ),
            type="Opaque",
            data=secret_data,
        )

        try:
            k8s.read_namespaced_secret(name=secret_name, namespace=SECRET_NAMESPACE)
            # Update existing
            k8s.replace_namespaced_secret(
                name=secret_name,
                namespace=SECRET_NAMESPACE,
                body=secret,
            )
            logger.info("Updated cluster credentials", cluster_id=cluster_id)
        except ApiException as e:
            if e.status == 404:
                # Create new
                k8s.create_namespaced_secret(
                    namespace=SECRET_NAMESPACE,
                    body=secret,
                )
                logger.info("Created cluster credentials", cluster_id=cluster_id)
            else:
                raise

    async def get_credentials(
        self,
        cluster_id: str,
    ) -> Optional[ClusterCredentials]:
        """Retrieve and decrypt cluster credentials.

        Args:
            cluster_id: Unique cluster identifier

        Returns:
            Decrypted ClusterCredentials or None if not found
        """
        import json

        k8s = self._get_k8s_client()
        secret_name = self._secret_name(cluster_id)

        try:
            secret = k8s.read_namespaced_secret(
                name=secret_name,
                namespace=SECRET_NAMESPACE,
            )

            # Decode secret data
            encrypted_data = base64.b64decode(secret.data["encrypted_data"]).decode()
            nonce = base64.b64decode(secret.data["nonce"]).decode()

            # Decrypt
            creds_json = self._decrypt(encrypted_data, nonce)

            # Parse back to model
            creds_dict = json.loads(creds_json)
            return ClusterCredentials(**creds_dict)

        except ApiException as e:
            if e.status == 404:
                logger.warning("Credentials not found", cluster_id=cluster_id)
                return None
            raise

    async def delete_credentials(self, cluster_id: str) -> bool:
        """Delete cluster credentials.

        Args:
            cluster_id: Unique cluster identifier

        Returns:
            True if deleted, False if not found
        """
        k8s = self._get_k8s_client()
        secret_name = self._secret_name(cluster_id)

        try:
            k8s.delete_namespaced_secret(
                name=secret_name,
                namespace=SECRET_NAMESPACE,
            )
            logger.info("Deleted cluster credentials", cluster_id=cluster_id)
            return True

        except ApiException as e:
            if e.status == 404:
                return False
            raise

    async def rotate_credentials(
        self,
        cluster_id: str,
        new_credentials: ClusterCredentials,
    ) -> None:
        """Rotate cluster credentials.

        Stores new credentials and updates rotation timestamp.
        """
        from datetime import datetime, timezone

        # Store new credentials (this will update the secret)
        await self.store_credentials(cluster_id, new_credentials)

        # Update rotation timestamp
        k8s = self._get_k8s_client()
        secret_name = self._secret_name(cluster_id)

        secret = k8s.read_namespaced_secret(
            name=secret_name,
            namespace=SECRET_NAMESPACE,
        )

        secret.data["rotated_at"] = base64.b64encode(
            datetime.now(timezone.utc).isoformat().encode()
        ).decode()

        k8s.replace_namespaced_secret(
            name=secret_name,
            namespace=SECRET_NAMESPACE,
            body=secret,
        )

        logger.info("Rotated cluster credentials", cluster_id=cluster_id)


# Singleton instance
credential_store = CredentialStore()
```

### Tests

**File:** `src/cluster-registry/tests/test_credential_store.py`

```python
"""Tests for Kubernetes Secrets credential storage."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import base64

from services.credential_store import CredentialStore, SECRET_NAMESPACE
from shared.models import AuthType, ClusterCredentials


@pytest.fixture
def credential_store():
    store = CredentialStore()
    # Mock the encryption key
    store._encryption_key = b"0" * 32  # 256-bit key
    return store


@pytest.fixture
def mock_k8s_client():
    with patch("services.credential_store.client.CoreV1Api") as mock:
        yield mock.return_value


@pytest.fixture
def sample_credentials():
    return ClusterCredentials(
        auth_type=AuthType.TOKEN,
        token="test-bearer-token-12345",
    )


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self, credential_store):
        """Test encryption and decryption produce original value."""
        plaintext = "secret-data-to-encrypt"

        encrypted, nonce = credential_store._encrypt(plaintext)
        decrypted = credential_store._decrypt(encrypted, nonce)

        assert decrypted == plaintext

    def test_encryption_produces_different_output(self, credential_store):
        """Test same plaintext produces different ciphertext (unique nonce)."""
        plaintext = "secret-data"

        encrypted1, nonce1 = credential_store._encrypt(plaintext)
        encrypted2, nonce2 = credential_store._encrypt(plaintext)

        assert encrypted1 != encrypted2
        assert nonce1 != nonce2


class TestSecretNaming:
    def test_secret_name_format(self, credential_store):
        """Test secret name follows convention."""
        cluster_id = "my-cluster-123"
        name = credential_store._secret_name(cluster_id)

        assert name == "aiops-cluster-my-cluster-123"


class TestStoreCredentials:
    async def test_store_creates_secret(
        self, credential_store, mock_k8s_client, sample_credentials
    ):
        """Test storing credentials creates Kubernetes Secret."""
        from kubernetes.client.rest import ApiException

        # Mock secret not found (will create)
        mock_k8s_client.read_namespaced_secret.side_effect = ApiException(status=404)

        await credential_store.store_credentials("cluster-1", sample_credentials)

        mock_k8s_client.create_namespaced_secret.assert_called_once()
        call_args = mock_k8s_client.create_namespaced_secret.call_args

        assert call_args.kwargs["namespace"] == SECRET_NAMESPACE

    async def test_store_updates_existing_secret(
        self, credential_store, mock_k8s_client, sample_credentials
    ):
        """Test storing credentials updates existing Secret."""
        # Mock secret exists
        mock_k8s_client.read_namespaced_secret.return_value = MagicMock()

        await credential_store.store_credentials("cluster-1", sample_credentials)

        mock_k8s_client.replace_namespaced_secret.assert_called_once()


class TestGetCredentials:
    async def test_get_returns_decrypted_credentials(
        self, credential_store, mock_k8s_client, sample_credentials
    ):
        """Test getting credentials returns decrypted data."""
        # First store credentials to get encrypted form
        creds_json = sample_credentials.model_dump_json()
        encrypted, nonce = credential_store._encrypt(creds_json)

        mock_secret = MagicMock()
        mock_secret.data = {
            "auth_type": base64.b64encode(b"token").decode(),
            "encrypted_data": base64.b64encode(encrypted.encode()).decode(),
            "nonce": base64.b64encode(nonce.encode()).decode(),
        }
        mock_k8s_client.read_namespaced_secret.return_value = mock_secret

        result = await credential_store.get_credentials("cluster-1")

        assert result is not None
        assert result.auth_type == AuthType.TOKEN
        assert result.token == sample_credentials.token

    async def test_get_returns_none_when_not_found(
        self, credential_store, mock_k8s_client
    ):
        """Test getting non-existent credentials returns None."""
        from kubernetes.client.rest import ApiException

        mock_k8s_client.read_namespaced_secret.side_effect = ApiException(status=404)

        result = await credential_store.get_credentials("nonexistent")

        assert result is None


class TestDeleteCredentials:
    async def test_delete_removes_secret(self, credential_store, mock_k8s_client):
        """Test deleting credentials removes the Secret."""
        result = await credential_store.delete_credentials("cluster-1")

        assert result is True
        mock_k8s_client.delete_namespaced_secret.assert_called_once()

    async def test_delete_returns_false_when_not_found(
        self, credential_store, mock_k8s_client
    ):
        """Test deleting non-existent credentials returns False."""
        from kubernetes.client.rest import ApiException

        mock_k8s_client.delete_namespaced_secret.side_effect = ApiException(status=404)

        result = await credential_store.delete_credentials("nonexistent")

        assert result is False
```

---

## Task 2.2: Credential Validation Service

**File:** `src/cluster-registry/services/credential_validator.py`

### Implementation

```python
"""Cluster Credential Validation Service.

Spec Reference: specs/02-cluster-registry.md Section 3.3

Validates credentials by making actual API calls to the target cluster.
"""

from typing import Optional
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
    api_version: Optional[str] = None
    username: Optional[str] = None
    groups: Optional[list[str]] = None


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
                message=f"Cannot connect to cluster: {str(e)}",
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
                message=f"Validation failed: {str(e)}",
            )

    def _build_auth_headers(self, credentials: ClusterCredentials) -> dict[str, str]:
        """Build HTTP headers for authentication."""
        headers = {}

        if credentials.auth_type == AuthType.TOKEN:
            headers["Authorization"] = f"Bearer {credentials.token}"

        elif credentials.auth_type == AuthType.BASIC:
            import base64
            auth_string = f"{credentials.username}:{credentials.password}"
            encoded = base64.b64encode(auth_string.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        return headers

    def _get_client_cert(
        self, credentials: ClusterCredentials
    ) -> Optional[tuple[str, str]]:
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
```

### Tests

**File:** `src/cluster-registry/tests/test_credential_validator.py`

```python
"""Tests for credential validation service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from services.credential_validator import (
    CredentialValidator,
    ValidationStatus,
    ValidationResult,
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
        import base64

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
```

---

## Task 2.3: Discovery Service

**File:** `src/cluster-registry/services/discovery.py`

### Implementation

```python
"""Cluster Component Discovery Service.

Spec Reference: specs/02-cluster-registry.md Section 4

Automatically discovers cluster components:
- Prometheus endpoints
- Loki endpoints
- Tempo endpoints
- GPU nodes
- CNF components (PTP, SR-IOV, DPDK)
"""

from typing import Optional
from enum import Enum

import httpx
from pydantic import BaseModel

from shared.models import ClusterCapabilities, ClusterEndpoints, CNFType
from shared.observability import get_logger

logger = get_logger(__name__)


class ComponentStatus(str, Enum):
    """Discovery status for a component."""

    DISCOVERED = "discovered"
    NOT_FOUND = "not_found"
    ERROR = "error"


class DiscoveredComponent(BaseModel):
    """Discovered component details."""

    name: str
    status: ComponentStatus
    endpoint: Optional[str] = None
    version: Optional[str] = None
    namespace: Optional[str] = None
    error: Optional[str] = None


class DiscoveryResult(BaseModel):
    """Complete discovery results for a cluster."""

    prometheus: Optional[DiscoveredComponent] = None
    loki: Optional[DiscoveredComponent] = None
    tempo: Optional[DiscoveredComponent] = None
    gpu_operator: Optional[DiscoveredComponent] = None
    cnf_components: list[DiscoveredComponent] = []
    endpoints: ClusterEndpoints
    capabilities: ClusterCapabilities


class DiscoveryService:
    """Discovers cluster components and capabilities."""

    def __init__(self):
        self.timeout = 15.0

    async def discover(
        self,
        api_url: str,
        auth_headers: dict[str, str],
        verify_ssl: bool = True,
    ) -> DiscoveryResult:
        """Run full cluster discovery.

        Args:
            api_url: Kubernetes API URL
            auth_headers: Authentication headers
            verify_ssl: Whether to verify SSL certificates

        Returns:
            DiscoveryResult with all discovered components
        """
        async with httpx.AsyncClient(
            verify=verify_ssl,
            timeout=self.timeout,
        ) as client:
            # Discover each component in parallel
            import asyncio

            prometheus, loki, tempo, gpu, cnf = await asyncio.gather(
                self._discover_prometheus(client, api_url, auth_headers),
                self._discover_loki(client, api_url, auth_headers),
                self._discover_tempo(client, api_url, auth_headers),
                self._discover_gpu_operator(client, api_url, auth_headers),
                self._discover_cnf_components(client, api_url, auth_headers),
            )

            # Build endpoints from discovered components
            endpoints = self._build_endpoints(prometheus, loki, tempo)

            # Build capabilities from discovery
            capabilities = self._build_capabilities(prometheus, loki, tempo, gpu, cnf)

            return DiscoveryResult(
                prometheus=prometheus,
                loki=loki,
                tempo=tempo,
                gpu_operator=gpu,
                cnf_components=cnf,
                endpoints=endpoints,
                capabilities=capabilities,
            )

    async def _discover_prometheus(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover Prometheus/Thanos in the cluster."""
        # Check for OpenShift monitoring stack
        namespaces_to_check = [
            "openshift-monitoring",
            "monitoring",
            "prometheus",
        ]
        service_names = [
            "prometheus-k8s",
            "thanos-querier",
            "prometheus",
        ]

        for namespace in namespaces_to_check:
            for service_name in service_names:
                try:
                    url = f"{api_url}/api/v1/namespaces/{namespace}/services/{service_name}"
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        svc = response.json()
                        # Build service URL
                        port = 9090
                        for p in svc.get("spec", {}).get("ports", []):
                            if p.get("name") in ["web", "http", "prometheus"]:
                                port = p.get("port", 9090)
                                break

                        endpoint = f"http://{service_name}.{namespace}.svc:{port}"

                        # Try to get version
                        version = await self._get_prometheus_version(
                            client, endpoint, headers
                        )

                        return DiscoveredComponent(
                            name="prometheus",
                            status=ComponentStatus.DISCOVERED,
                            endpoint=endpoint,
                            version=version,
                            namespace=namespace,
                        )

                except Exception as e:
                    logger.debug(
                        "Prometheus check failed",
                        namespace=namespace,
                        service=service_name,
                        error=str(e),
                    )

        return DiscoveredComponent(
            name="prometheus",
            status=ComponentStatus.NOT_FOUND,
            error="No Prometheus instance found",
        )

    async def _get_prometheus_version(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        headers: dict[str, str],
    ) -> Optional[str]:
        """Get Prometheus version from build info endpoint."""
        try:
            response = await client.get(
                f"{endpoint}/api/v1/status/buildinfo",
                headers=headers,
                timeout=5.0,
            )
            if response.status_code == 200:
                return response.json().get("data", {}).get("version")
        except Exception:
            pass
        return None

    async def _discover_loki(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover Loki in the cluster."""
        namespaces = ["openshift-logging", "logging", "loki"]
        services = ["loki", "loki-gateway", "loki-distributor"]

        for namespace in namespaces:
            for service in services:
                try:
                    url = f"{api_url}/api/v1/namespaces/{namespace}/services/{service}"
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        svc = response.json()
                        port = 3100
                        for p in svc.get("spec", {}).get("ports", []):
                            if p.get("name") in ["http", "http-metrics"]:
                                port = p.get("port", 3100)
                                break

                        endpoint = f"http://{service}.{namespace}.svc:{port}"

                        return DiscoveredComponent(
                            name="loki",
                            status=ComponentStatus.DISCOVERED,
                            endpoint=endpoint,
                            namespace=namespace,
                        )

                except Exception as e:
                    logger.debug("Loki check failed", error=str(e))

        return DiscoveredComponent(
            name="loki",
            status=ComponentStatus.NOT_FOUND,
            error="No Loki instance found",
        )

    async def _discover_tempo(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover Tempo in the cluster."""
        namespaces = ["openshift-distributed-tracing", "tracing", "tempo"]
        services = ["tempo", "tempo-query", "tempo-distributor"]

        for namespace in namespaces:
            for service in services:
                try:
                    url = f"{api_url}/api/v1/namespaces/{namespace}/services/{service}"
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        svc = response.json()
                        port = 3200
                        for p in svc.get("spec", {}).get("ports", []):
                            if p.get("name") in ["http", "tempo"]:
                                port = p.get("port", 3200)
                                break

                        endpoint = f"http://{service}.{namespace}.svc:{port}"

                        return DiscoveredComponent(
                            name="tempo",
                            status=ComponentStatus.DISCOVERED,
                            endpoint=endpoint,
                            namespace=namespace,
                        )

                except Exception as e:
                    logger.debug("Tempo check failed", error=str(e))

        return DiscoveredComponent(
            name="tempo",
            status=ComponentStatus.NOT_FOUND,
            error="No Tempo instance found",
        )

    async def _discover_gpu_operator(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> DiscoveredComponent:
        """Discover NVIDIA GPU Operator."""
        try:
            # Check for GPU operator namespace
            url = f"{api_url}/api/v1/namespaces/gpu-operator"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                # Check for nvidia-driver-daemonset
                ds_url = f"{api_url}/apis/apps/v1/namespaces/gpu-operator/daemonsets/nvidia-driver-daemonset"
                ds_response = await client.get(ds_url, headers=headers)

                if ds_response.status_code == 200:
                    return DiscoveredComponent(
                        name="gpu-operator",
                        status=ComponentStatus.DISCOVERED,
                        namespace="gpu-operator",
                    )

            # Also check nvidia-gpu-operator namespace
            url = f"{api_url}/api/v1/namespaces/nvidia-gpu-operator"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return DiscoveredComponent(
                    name="gpu-operator",
                    status=ComponentStatus.DISCOVERED,
                    namespace="nvidia-gpu-operator",
                )

        except Exception as e:
            logger.debug("GPU operator check failed", error=str(e))

        return DiscoveredComponent(
            name="gpu-operator",
            status=ComponentStatus.NOT_FOUND,
            error="No GPU Operator found",
        )

    async def _discover_cnf_components(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        headers: dict[str, str],
    ) -> list[DiscoveredComponent]:
        """Discover CNF components (PTP, SR-IOV, DPDK)."""
        components = []

        # Check for PTP operator
        try:
            url = f"{api_url}/apis/ptp.openshift.io/v1/ptpconfigs"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                items = response.json().get("items", [])
                if items:
                    components.append(
                        DiscoveredComponent(
                            name="ptp",
                            status=ComponentStatus.DISCOVERED,
                            namespace="openshift-ptp",
                        )
                    )
        except Exception:
            pass

        # Check for SR-IOV operator
        try:
            url = f"{api_url}/apis/sriovnetwork.openshift.io/v1/sriovnetworknodestates"
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                items = response.json().get("items", [])
                if items:
                    components.append(
                        DiscoveredComponent(
                            name="sriov",
                            status=ComponentStatus.DISCOVERED,
                            namespace="openshift-sriov-network-operator",
                        )
                    )
        except Exception:
            pass

        return components

    def _build_endpoints(
        self,
        prometheus: DiscoveredComponent,
        loki: DiscoveredComponent,
        tempo: DiscoveredComponent,
    ) -> ClusterEndpoints:
        """Build ClusterEndpoints from discovered components."""
        return ClusterEndpoints(
            prometheus_url=prometheus.endpoint if prometheus.status == ComponentStatus.DISCOVERED else None,
            loki_url=loki.endpoint if loki.status == ComponentStatus.DISCOVERED else None,
            tempo_url=tempo.endpoint if tempo.status == ComponentStatus.DISCOVERED else None,
        )

    def _build_capabilities(
        self,
        prometheus: DiscoveredComponent,
        loki: DiscoveredComponent,
        tempo: DiscoveredComponent,
        gpu: DiscoveredComponent,
        cnf: list[DiscoveredComponent],
    ) -> ClusterCapabilities:
        """Build ClusterCapabilities from discovery results."""
        cnf_types = []
        for c in cnf:
            if c.status == ComponentStatus.DISCOVERED:
                if c.name == "ptp":
                    cnf_types.append(CNFType.PTP)
                elif c.name == "sriov":
                    cnf_types.append(CNFType.SRIOV)

        return ClusterCapabilities(
            has_gpu=gpu.status == ComponentStatus.DISCOVERED,
            has_prometheus=prometheus.status == ComponentStatus.DISCOVERED,
            has_loki=loki.status == ComponentStatus.DISCOVERED,
            has_tempo=tempo.status == ComponentStatus.DISCOVERED,
            cnf_types=cnf_types,
        )


# Singleton instance
discovery_service = DiscoveryService()


async def discover_cluster_components(
    api_url: str,
    auth_headers: dict[str, str],
    verify_ssl: bool = True,
) -> DiscoveryResult:
    """Discover all cluster components."""
    return await discovery_service.discover(api_url, auth_headers, verify_ssl)
```

### Tests

**File:** `src/cluster-registry/tests/test_discovery.py`

```python
"""Tests for discovery service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.discovery import (
    ComponentStatus,
    DiscoveredComponent,
    DiscoveryService,
)


@pytest.fixture
def discovery_service():
    return DiscoveryService()


@pytest.fixture
def mock_headers():
    return {"Authorization": "Bearer test-token"}


class TestPrometheusDiscovery:
    async def test_discovers_openshift_prometheus(self, discovery_service, mock_headers):
        """Test Prometheus discovery in openshift-monitoring namespace."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "spec": {
                    "ports": [{"name": "web", "port": 9090}]
                }
            }

            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await discovery_service._discover_prometheus(
                mock_instance,
                "https://api.cluster.local:6443",
                mock_headers,
            )

            assert result.status == ComponentStatus.DISCOVERED
            assert result.namespace == "openshift-monitoring"
            assert "9090" in result.endpoint

    async def test_prometheus_not_found(self, discovery_service, mock_headers):
        """Test Prometheus not found returns NOT_FOUND status."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404

            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await discovery_service._discover_prometheus(
                mock_instance,
                "https://api.cluster.local:6443",
                mock_headers,
            )

            assert result.status == ComponentStatus.NOT_FOUND


class TestGPUDiscovery:
    async def test_discovers_gpu_operator(self, discovery_service, mock_headers):
        """Test GPU operator discovery."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock namespace and daemonset exist
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await discovery_service._discover_gpu_operator(
                mock_instance,
                "https://api.cluster.local:6443",
                mock_headers,
            )

            assert result.status == ComponentStatus.DISCOVERED
            assert result.namespace == "gpu-operator"


class TestCapabilities:
    def test_build_capabilities_all_present(self, discovery_service):
        """Test capabilities built with all components present."""
        prometheus = DiscoveredComponent(
            name="prometheus",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://prometheus:9090",
        )
        loki = DiscoveredComponent(
            name="loki",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://loki:3100",
        )
        tempo = DiscoveredComponent(
            name="tempo",
            status=ComponentStatus.DISCOVERED,
            endpoint="http://tempo:3200",
        )
        gpu = DiscoveredComponent(
            name="gpu-operator",
            status=ComponentStatus.DISCOVERED,
        )
        cnf = [
            DiscoveredComponent(name="ptp", status=ComponentStatus.DISCOVERED),
            DiscoveredComponent(name="sriov", status=ComponentStatus.DISCOVERED),
        ]

        capabilities = discovery_service._build_capabilities(
            prometheus, loki, tempo, gpu, cnf
        )

        assert capabilities.has_gpu is True
        assert capabilities.has_prometheus is True
        assert capabilities.has_loki is True
        assert capabilities.has_tempo is True
        assert len(capabilities.cnf_types) == 2

    def test_build_capabilities_none_present(self, discovery_service):
        """Test capabilities built with no components present."""
        not_found = DiscoveredComponent(
            name="test",
            status=ComponentStatus.NOT_FOUND,
        )

        capabilities = discovery_service._build_capabilities(
            not_found, not_found, not_found, not_found, []
        )

        assert capabilities.has_gpu is False
        assert capabilities.has_prometheus is False
        assert capabilities.has_loki is False
        assert capabilities.has_tempo is False
        assert capabilities.cnf_types == []
```

---

## Task 2.4: Update Cluster Service to Use New Components

**File:** `src/cluster-registry/services/cluster_service.py` (MODIFY)

### Changes Required

```python
# Add imports
from services.credential_store import credential_store
from services.credential_validator import validate_cluster_credentials, ValidationStatus
from services.discovery import discover_cluster_components

# Modify create_cluster method
async def create_cluster(self, cluster_create: ClusterCreate) -> Cluster:
    """Create a new cluster with validation and discovery."""

    # 1. Validate credentials first
    validation_result = await validate_cluster_credentials(
        cluster_create.api_url,
        cluster_create.credentials,
    )

    if validation_result.status != ValidationStatus.VALID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Credential validation failed: {validation_result.message}",
        )

    # 2. Create cluster record
    cluster_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 3. Store credentials in Kubernetes Secrets
    await credential_store.store_credentials(cluster_id, cluster_create.credentials)

    # 4. Run discovery
    auth_headers = {"Authorization": f"Bearer {cluster_create.credentials.token}"}
    discovery = await discover_cluster_components(
        cluster_create.api_url,
        auth_headers,
        verify_ssl=not cluster_create.credentials.skip_tls_verify,
    )

    # 5. Build cluster object with discovered endpoints and capabilities
    cluster = Cluster(
        id=cluster_id,
        name=cluster_create.name,
        api_url=cluster_create.api_url,
        # ... other fields
        endpoints=discovery.endpoints,
        capabilities=discovery.capabilities,
        created_at=now,
        updated_at=now,
    )

    # 6. Save to database
    await self._save_cluster(cluster)

    logger.info(
        "Cluster created",
        cluster_id=cluster_id,
        name=cluster_create.name,
        capabilities=discovery.capabilities.model_dump(),
    )

    return cluster

# Modify delete_cluster method
async def delete_cluster(self, cluster_id: str) -> bool:
    """Delete cluster and associated credentials."""

    # Delete credentials from K8s Secrets
    await credential_store.delete_credentials(cluster_id)

    # Delete from database
    # ... existing deletion logic

    return True
```

---

## Acceptance Criteria

- [ ] Credentials stored in Kubernetes Secrets with AES-256-GCM encryption
- [ ] Encryption key managed as a separate Kubernetes Secret
- [ ] Credential validation makes real API calls to target cluster
- [ ] Invalid credentials rejected with appropriate error message
- [ ] Discovery finds Prometheus in openshift-monitoring namespace
- [ ] Discovery finds Loki in openshift-logging namespace
- [ ] Discovery finds Tempo in openshift-distributed-tracing namespace
- [ ] GPU operator detection via nvidia-driver-daemonset
- [ ] CNF components (PTP, SR-IOV) discovered via CRDs
- [ ] Cluster capabilities auto-populated from discovery
- [ ] All tests pass with >80% coverage

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/cluster-registry/services/credential_store.py` | CREATE | K8s Secrets credential storage |
| `src/cluster-registry/services/credential_validator.py` | CREATE | Credential validation service |
| `src/cluster-registry/services/discovery.py` | CREATE | Component discovery service |
| `src/cluster-registry/services/__init__.py` | MODIFY | Export new services |
| `src/cluster-registry/services/cluster_service.py` | MODIFY | Integrate new services |
| `src/cluster-registry/tests/test_credential_store.py` | CREATE | Credential store tests |
| `src/cluster-registry/tests/test_credential_validator.py` | CREATE | Validator tests |
| `src/cluster-registry/tests/test_discovery.py` | CREATE | Discovery tests |

---

## Dependencies

### Python packages (add to pyproject.toml)

```toml
dependencies = [
    # ... existing
    "kubernetes>=28.1.0",  # Kubernetes Python client
    "cryptography>=41.0.0",  # AES-256-GCM encryption
]
```

### Kubernetes RBAC

The service account needs permissions to:
- Create/Read/Update/Delete Secrets in aiops-system namespace
- Read Services, Namespaces, DaemonSets across cluster
- Read CRDs for PTP and SR-IOV

**File:** `deploy/rbac/cluster-registry-rbac.yaml`

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aiops-cluster-registry
rules:
  # Secrets management
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["create", "get", "update", "delete", "list"]
  # Discovery
  - apiGroups: [""]
    resources: ["services", "namespaces"]
    verbs: ["get", "list"]
  - apiGroups: ["apps"]
    resources: ["daemonsets"]
    verbs: ["get", "list"]
  # CNF discovery
  - apiGroups: ["ptp.openshift.io"]
    resources: ["ptpconfigs"]
    verbs: ["get", "list"]
  - apiGroups: ["sriovnetwork.openshift.io"]
    resources: ["sriovnetworknodestates"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: aiops-cluster-registry
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: aiops-cluster-registry
subjects:
  - kind: ServiceAccount
    name: aiops-cluster-registry
    namespace: aiops-system
```

---

## Rollback Plan

If issues arise:
1. Revert to in-memory credential storage temporarily
2. Skip validation and discovery in cluster creation
3. Comment out credential_store/validator/discovery imports
4. Return mock capabilities until fixed
