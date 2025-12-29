"""Kubernetes Secrets-based Credential Storage.

Spec Reference: specs/02-cluster-registry.md Section 3.2

Credentials are stored in Kubernetes Secrets with:
- AES-256-GCM encryption for sensitive fields
- Namespace isolation per cluster
- Automatic rotation support
"""

import base64
import os
from datetime import UTC, datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from pydantic import BaseModel

from shared.models import AuthType, ClusterCredentials
from shared.observability import get_logger

logger = get_logger(__name__)

# Secret naming convention
SECRET_NAME_PREFIX = "aiops-cluster-"
SECRET_NAMESPACE = "aiops-nextgen"
ENCRYPTION_KEY_SECRET = "aiops-encryption-key"


class EncryptedCredential(BaseModel):
    """Encrypted credential data structure."""

    auth_type: AuthType
    encrypted_data: str  # Base64 encoded encrypted JSON
    nonce: str  # Base64 encoded nonce
    created_at: str
    rotated_at: str | None = None


class CredentialStore:
    """Kubernetes Secrets-based credential storage with encryption."""

    def __init__(self):
        self._encryption_key: bytes | None = None
        self._k8s_client: client.CoreV1Api | None = None

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

        k8s = self._get_k8s_client()
        secret_name = self._secret_name(cluster_id)

        # Serialize credentials to JSON
        creds_json = credentials.model_dump_json()

        # Encrypt the JSON
        encrypted_data, nonce = self._encrypt(creds_json)

        # Build secret data
        # Handle both enum and string auth_type
        auth_type_value = credentials.auth_type.value if hasattr(credentials.auth_type, "value") else str(credentials.auth_type)
        secret_data = {
            "auth_type": base64.b64encode(auth_type_value.encode()).decode(),
            "encrypted_data": base64.b64encode(encrypted_data.encode()).decode(),
            "nonce": base64.b64encode(nonce.encode()).decode(),
            "created_at": base64.b64encode(
                datetime.now(UTC).isoformat().encode()
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
                    "aiops.io/auth-type": auth_type_value,
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
    ) -> ClusterCredentials | None:
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
            datetime.now(UTC).isoformat().encode()
        ).decode()

        k8s.replace_namespaced_secret(
            name=secret_name,
            namespace=SECRET_NAMESPACE,
            body=secret,
        )

        logger.info("Rotated cluster credentials", cluster_id=cluster_id)


# Singleton instance
credential_store = CredentialStore()
