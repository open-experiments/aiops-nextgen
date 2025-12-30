"""Tests for Kubernetes Secrets credential storage."""

import base64
from unittest.mock import MagicMock, patch

import pytest
from app.services.credential_store import SECRET_NAMESPACE, CredentialStore
from kubernetes.client.rest import ApiException

from shared.models import AuthType, ClusterCredentials


@pytest.fixture
def credential_store():
    store = CredentialStore()
    # Mock the encryption key
    store._encryption_key = b"0" * 32  # 256-bit key
    return store


@pytest.fixture
def mock_k8s_client():
    with patch("app.services.credential_store.client.CoreV1Api") as mock:
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
        # Mock secret not found (will create)
        mock_k8s_client.read_namespaced_secret.side_effect = ApiException(status=404)
        credential_store._k8s_client = mock_k8s_client

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
        credential_store._k8s_client = mock_k8s_client

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
            "auth_type": base64.b64encode(b"TOKEN").decode(),
            "encrypted_data": base64.b64encode(encrypted.encode()).decode(),
            "nonce": base64.b64encode(nonce.encode()).decode(),
        }
        mock_k8s_client.read_namespaced_secret.return_value = mock_secret
        credential_store._k8s_client = mock_k8s_client

        result = await credential_store.get_credentials("cluster-1")

        assert result is not None
        assert result.auth_type == AuthType.TOKEN
        assert result.token == sample_credentials.token

    async def test_get_returns_none_when_not_found(self, credential_store, mock_k8s_client):
        """Test getting non-existent credentials returns None."""
        mock_k8s_client.read_namespaced_secret.side_effect = ApiException(status=404)
        credential_store._k8s_client = mock_k8s_client

        result = await credential_store.get_credentials("nonexistent")

        assert result is None


class TestDeleteCredentials:
    async def test_delete_removes_secret(self, credential_store, mock_k8s_client):
        """Test deleting credentials removes the Secret."""
        credential_store._k8s_client = mock_k8s_client

        result = await credential_store.delete_credentials("cluster-1")

        assert result is True
        mock_k8s_client.delete_namespaced_secret.assert_called_once()

    async def test_delete_returns_false_when_not_found(self, credential_store, mock_k8s_client):
        """Test deleting non-existent credentials returns False."""
        mock_k8s_client.delete_namespaced_secret.side_effect = ApiException(status=404)
        credential_store._k8s_client = mock_k8s_client

        result = await credential_store.delete_credentials("nonexistent")

        assert result is False
