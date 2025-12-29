# Sprint 1: Security Foundation

**Issues Addressed:** ISSUE-010 (CRITICAL), ISSUE-011 (CRITICAL), ISSUE-015 (HIGH)
**Priority:** P0 - BLOCKING
**Dependencies:** None (Foundation Sprint)

---

## Overview

This sprint implements OAuth 2.0 authentication via OpenShift, RBAC authorization, and WebSocket authentication. All subsequent sprints depend on this security layer.

---

## Task 1.1: OAuth Authentication Middleware

**File:** `src/api-gateway/middleware/oauth.py`

### Implementation

```python
"""OAuth 2.0 Authentication Middleware.

Spec Reference: specs/06-api-gateway.md Section 3.1
"""

import time
from typing import Optional

import httpx
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload from OpenShift OAuth."""

    sub: str  # User ID
    preferred_username: str
    email: Optional[str] = None
    groups: list[str] = []
    exp: int
    iat: int
    iss: str


class OAuthConfig(BaseModel):
    """OAuth provider configuration."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str


class OAuthMiddleware:
    """OAuth 2.0 authentication middleware for OpenShift integration."""

    def __init__(self):
        self.settings = get_settings()
        self._jwks_cache: Optional[dict] = None
        self._jwks_cache_time: float = 0
        self._jwks_cache_ttl: int = 3600  # 1 hour
        self._config_cache: Optional[OAuthConfig] = None

    async def get_oauth_config(self) -> OAuthConfig:
        """Fetch OAuth provider configuration from well-known endpoint."""
        if self._config_cache:
            return self._config_cache

        well_known_url = f"{self.settings.oauth.issuer}/.well-known/oauth-authorization-server"

        async with httpx.AsyncClient(verify=True, timeout=10.0) as client:
            try:
                response = await client.get(well_known_url)
                response.raise_for_status()
                data = response.json()

                self._config_cache = OAuthConfig(
                    issuer=data["issuer"],
                    authorization_endpoint=data["authorization_endpoint"],
                    token_endpoint=data["token_endpoint"],
                    userinfo_endpoint=data["userinfo_endpoint"],
                    jwks_uri=data["jwks_uri"],
                )
                return self._config_cache
            except httpx.HTTPError as e:
                logger.error("Failed to fetch OAuth config", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="OAuth provider unavailable",
                )

    async def get_jwks(self) -> dict:
        """Fetch and cache JWKS from OAuth provider."""
        now = time.time()

        if self._jwks_cache and (now - self._jwks_cache_time) < self._jwks_cache_ttl:
            return self._jwks_cache

        config = await self.get_oauth_config()

        async with httpx.AsyncClient(verify=True, timeout=10.0) as client:
            try:
                response = await client.get(config.jwks_uri)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = now
                return self._jwks_cache
            except httpx.HTTPError as e:
                logger.error("Failed to fetch JWKS", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Unable to validate token",
                )

    async def validate_token(self, token: str) -> TokenPayload:
        """Validate JWT token and return payload."""
        try:
            # Get JWKS for signature verification
            jwks = await self.get_jwks()

            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            # Find matching key
            rsa_key = None
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

            if not rsa_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unable to find appropriate key",
                )

            # Verify and decode token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                issuer=self.settings.oauth.issuer,
                options={"verify_aud": False},  # OpenShift may not include aud
            )

            return TokenPayload(**payload)

        except JWTError as e:
            logger.warning("JWT validation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    async def __call__(self, request: Request) -> TokenPayload:
        """Extract and validate token from request."""
        # Skip auth for health endpoints
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return None

        # Get authorization header
        auth: Optional[HTTPAuthorizationCredentials] = await security(request)

        if not auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        token_payload = await self.validate_token(auth.credentials)

        # Attach user info to request state
        request.state.user = token_payload
        request.state.user_id = token_payload.sub
        request.state.username = token_payload.preferred_username
        request.state.groups = token_payload.groups

        logger.info(
            "User authenticated",
            user_id=token_payload.sub,
            username=token_payload.preferred_username,
        )

        return token_payload


# Singleton instance
oauth_middleware = OAuthMiddleware()


async def get_current_user(request: Request) -> TokenPayload:
    """Dependency to get current authenticated user."""
    return await oauth_middleware(request)
```

### Tests

**File:** `src/api-gateway/tests/test_oauth.py`

```python
"""Tests for OAuth middleware."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from jose import jwt
import time

from middleware.oauth import OAuthMiddleware, TokenPayload


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
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection failed")
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
```

---

## Task 1.2: RBAC Authorization Service

**File:** `src/api-gateway/services/rbac.py`

### Implementation

```python
"""Role-Based Access Control (RBAC) Service.

Spec Reference: specs/06-api-gateway.md Section 3.2

Roles:
- admin: Full access to all resources and operations
- operator: Read/write access to clusters and observability, read-only for settings
- viewer: Read-only access to all resources
"""

from enum import Enum
from typing import Optional

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from shared.observability import get_logger

logger = get_logger(__name__)


class Role(str, Enum):
    """User roles with hierarchical permissions."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    """Fine-grained permissions."""

    # Cluster permissions
    CLUSTER_READ = "cluster:read"
    CLUSTER_WRITE = "cluster:write"
    CLUSTER_DELETE = "cluster:delete"

    # Observability permissions
    METRICS_READ = "metrics:read"
    LOGS_READ = "logs:read"
    TRACES_READ = "traces:read"
    ALERTS_READ = "alerts:read"
    ALERTS_WRITE = "alerts:write"

    # Intelligence permissions
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    ANOMALY_READ = "anomaly:read"
    REPORTS_READ = "reports:read"
    REPORTS_WRITE = "reports:write"

    # Admin permissions
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions
    Role.OPERATOR: {
        Permission.CLUSTER_READ,
        Permission.CLUSTER_WRITE,
        Permission.METRICS_READ,
        Permission.LOGS_READ,
        Permission.TRACES_READ,
        Permission.ALERTS_READ,
        Permission.ALERTS_WRITE,
        Permission.CHAT_READ,
        Permission.CHAT_WRITE,
        Permission.ANOMALY_READ,
        Permission.REPORTS_READ,
        Permission.REPORTS_WRITE,
        Permission.SETTINGS_READ,
    },
    Role.VIEWER: {
        Permission.CLUSTER_READ,
        Permission.METRICS_READ,
        Permission.LOGS_READ,
        Permission.TRACES_READ,
        Permission.ALERTS_READ,
        Permission.CHAT_READ,
        Permission.ANOMALY_READ,
        Permission.REPORTS_READ,
        Permission.SETTINGS_READ,
    },
}

# OpenShift group to role mapping
GROUP_ROLE_MAPPING: dict[str, Role] = {
    "cluster-admins": Role.ADMIN,
    "aiops-admins": Role.ADMIN,
    "aiops-operators": Role.OPERATOR,
    "aiops-viewers": Role.VIEWER,
}


class UserContext(BaseModel):
    """User context with resolved role and permissions."""

    user_id: str
    username: str
    email: Optional[str] = None
    groups: list[str]
    role: Role
    permissions: set[Permission]


class RBACService:
    """RBAC authorization service."""

    def resolve_role(self, groups: list[str]) -> Role:
        """Resolve user role from OpenShift groups.

        Returns the highest privilege role matched from user groups.
        Defaults to VIEWER if no matching group found.
        """
        resolved_role = Role.VIEWER

        # Priority order: ADMIN > OPERATOR > VIEWER
        role_priority = {Role.ADMIN: 3, Role.OPERATOR: 2, Role.VIEWER: 1}

        for group in groups:
            if group in GROUP_ROLE_MAPPING:
                mapped_role = GROUP_ROLE_MAPPING[group]
                if role_priority[mapped_role] > role_priority[resolved_role]:
                    resolved_role = mapped_role

        return resolved_role

    def get_permissions(self, role: Role) -> set[Permission]:
        """Get permissions for a role."""
        return ROLE_PERMISSIONS.get(role, set())

    def build_user_context(
        self,
        user_id: str,
        username: str,
        groups: list[str],
        email: Optional[str] = None,
    ) -> UserContext:
        """Build complete user context with resolved permissions."""
        role = self.resolve_role(groups)
        permissions = self.get_permissions(role)

        return UserContext(
            user_id=user_id,
            username=username,
            email=email,
            groups=groups,
            role=role,
            permissions=permissions,
        )

    def check_permission(
        self,
        user_context: UserContext,
        required_permission: Permission,
    ) -> bool:
        """Check if user has required permission."""
        return required_permission in user_context.permissions

    def require_permission(
        self,
        user_context: UserContext,
        required_permission: Permission,
    ) -> None:
        """Require permission or raise 403 Forbidden."""
        if not self.check_permission(user_context, required_permission):
            logger.warning(
                "Permission denied",
                user_id=user_context.user_id,
                required=required_permission.value,
                role=user_context.role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {required_permission.value}",
            )

    def require_any_permission(
        self,
        user_context: UserContext,
        required_permissions: list[Permission],
    ) -> None:
        """Require any of the listed permissions or raise 403."""
        for perm in required_permissions:
            if self.check_permission(user_context, perm):
                return

        logger.warning(
            "Permission denied (none matched)",
            user_id=user_context.user_id,
            required=[ p.value for p in required_permissions],
            role=user_context.role.value,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    def require_role(
        self,
        user_context: UserContext,
        minimum_role: Role,
    ) -> None:
        """Require minimum role level or raise 403."""
        role_priority = {Role.ADMIN: 3, Role.OPERATOR: 2, Role.VIEWER: 1}

        if role_priority[user_context.role] < role_priority[minimum_role]:
            logger.warning(
                "Insufficient role",
                user_id=user_context.user_id,
                current_role=user_context.role.value,
                required_role=minimum_role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher",
            )


# Singleton instance
rbac_service = RBACService()


def get_user_context(request: Request) -> UserContext:
    """Dependency to get user context from request state."""
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = request.state.user
    return rbac_service.build_user_context(
        user_id=user.sub,
        username=user.preferred_username,
        email=user.email,
        groups=user.groups,
    )


def require_permission(permission: Permission):
    """Decorator factory for requiring a specific permission."""
    def dependency(request: Request) -> UserContext:
        user_context = get_user_context(request)
        rbac_service.require_permission(user_context, permission)
        return user_context
    return dependency


def require_role(minimum_role: Role):
    """Decorator factory for requiring a minimum role."""
    def dependency(request: Request) -> UserContext:
        user_context = get_user_context(request)
        rbac_service.require_role(user_context, minimum_role)
        return user_context
    return dependency
```

### Tests

**File:** `src/api-gateway/tests/test_rbac.py`

```python
"""Tests for RBAC service."""

import pytest
from fastapi import HTTPException

from services.rbac import (
    Permission,
    RBACService,
    Role,
    UserContext,
    GROUP_ROLE_MAPPING,
)


@pytest.fixture
def rbac_service():
    return RBACService()


class TestRoleResolution:
    def test_admin_group_resolves_to_admin(self, rbac_service):
        """Test cluster-admins group resolves to admin role."""
        groups = ["cluster-admins"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.ADMIN

    def test_operator_group_resolves_to_operator(self, rbac_service):
        """Test aiops-operators group resolves to operator role."""
        groups = ["aiops-operators"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.OPERATOR

    def test_viewer_group_resolves_to_viewer(self, rbac_service):
        """Test aiops-viewers group resolves to viewer role."""
        groups = ["aiops-viewers"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.VIEWER

    def test_unknown_group_defaults_to_viewer(self, rbac_service):
        """Test unknown groups default to viewer role."""
        groups = ["unknown-group", "another-unknown"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.VIEWER

    def test_highest_role_wins(self, rbac_service):
        """Test highest privilege role is selected when multiple match."""
        groups = ["aiops-viewers", "aiops-operators", "cluster-admins"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.ADMIN

    def test_empty_groups_defaults_to_viewer(self, rbac_service):
        """Test empty groups list defaults to viewer."""
        groups = []
        role = rbac_service.resolve_role(groups)
        assert role == Role.VIEWER


class TestPermissions:
    def test_admin_has_all_permissions(self, rbac_service):
        """Test admin role has all permissions."""
        permissions = rbac_service.get_permissions(Role.ADMIN)
        assert Permission.CLUSTER_DELETE in permissions
        assert Permission.USERS_WRITE in permissions
        assert Permission.SETTINGS_WRITE in permissions

    def test_operator_cannot_delete_clusters(self, rbac_service):
        """Test operator role cannot delete clusters."""
        permissions = rbac_service.get_permissions(Role.OPERATOR)
        assert Permission.CLUSTER_DELETE not in permissions
        assert Permission.CLUSTER_WRITE in permissions

    def test_viewer_is_read_only(self, rbac_service):
        """Test viewer role has only read permissions."""
        permissions = rbac_service.get_permissions(Role.VIEWER)

        for perm in permissions:
            assert "write" not in perm.value
            assert "delete" not in perm.value


class TestPermissionChecks:
    @pytest.fixture
    def admin_context(self, rbac_service):
        return rbac_service.build_user_context(
            user_id="admin-1",
            username="admin",
            groups=["cluster-admins"],
        )

    @pytest.fixture
    def viewer_context(self, rbac_service):
        return rbac_service.build_user_context(
            user_id="viewer-1",
            username="viewer",
            groups=["aiops-viewers"],
        )

    def test_require_permission_success(self, rbac_service, admin_context):
        """Test require_permission passes for authorized user."""
        # Should not raise
        rbac_service.require_permission(admin_context, Permission.CLUSTER_DELETE)

    def test_require_permission_failure(self, rbac_service, viewer_context):
        """Test require_permission raises for unauthorized user."""
        with pytest.raises(HTTPException) as exc_info:
            rbac_service.require_permission(viewer_context, Permission.CLUSTER_WRITE)

        assert exc_info.value.status_code == 403

    def test_require_role_success(self, rbac_service, admin_context):
        """Test require_role passes for sufficient role."""
        rbac_service.require_role(admin_context, Role.OPERATOR)

    def test_require_role_failure(self, rbac_service, viewer_context):
        """Test require_role raises for insufficient role."""
        with pytest.raises(HTTPException) as exc_info:
            rbac_service.require_role(viewer_context, Role.OPERATOR)

        assert exc_info.value.status_code == 403


class TestUserContext:
    def test_build_user_context(self, rbac_service):
        """Test building complete user context."""
        context = rbac_service.build_user_context(
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            groups=["aiops-operators"],
        )

        assert context.user_id == "user-123"
        assert context.role == Role.OPERATOR
        assert Permission.CLUSTER_WRITE in context.permissions
        assert Permission.CLUSTER_DELETE not in context.permissions
```

---

## Task 1.3: WebSocket Authentication

**File:** `src/realtime-streaming/middleware/ws_auth.py`

### Implementation

```python
"""WebSocket Authentication Middleware.

Spec Reference: specs/05-realtime-streaming.md Section 4
"""

from typing import Optional
from urllib.parse import parse_qs

import httpx
from fastapi import WebSocket, WebSocketException, status
from jose import JWTError, jwt
from pydantic import BaseModel

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class WSTokenPayload(BaseModel):
    """WebSocket token payload."""

    sub: str
    preferred_username: str
    groups: list[str] = []
    exp: int


class WebSocketAuthenticator:
    """WebSocket connection authenticator."""

    def __init__(self):
        self.settings = get_settings()
        self._jwks_cache: Optional[dict] = None

    async def get_jwks(self) -> dict:
        """Fetch JWKS from OAuth provider."""
        if self._jwks_cache:
            return self._jwks_cache

        well_known_url = f"{self.settings.oauth.issuer}/.well-known/oauth-authorization-server"

        async with httpx.AsyncClient(verify=True, timeout=10.0) as client:
            config_response = await client.get(well_known_url)
            config_response.raise_for_status()
            config = config_response.json()

            jwks_response = await client.get(config["jwks_uri"])
            jwks_response.raise_for_status()
            self._jwks_cache = jwks_response.json()

            return self._jwks_cache

    def extract_token(self, websocket: WebSocket) -> Optional[str]:
        """Extract token from WebSocket connection.

        Token can be provided via:
        1. Query parameter: ?token=xxx
        2. Sec-WebSocket-Protocol header: bearer, <token>
        """
        # Try query parameter first
        query_string = websocket.scope.get("query_string", b"").decode()
        params = parse_qs(query_string)

        if "token" in params:
            return params["token"][0]

        # Try Sec-WebSocket-Protocol header
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        if protocols.startswith("bearer,"):
            parts = protocols.split(",", 1)
            if len(parts) == 2:
                return parts[1].strip()

        return None

    async def validate_token(self, token: str) -> WSTokenPayload:
        """Validate JWT token."""
        try:
            jwks = await self.get_jwks()

            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            rsa_key = None
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

            if not rsa_key:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid token signing key",
                )

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                issuer=self.settings.oauth.issuer,
                options={"verify_aud": False},
            )

            return WSTokenPayload(**payload)

        except JWTError as e:
            logger.warning("WebSocket JWT validation failed", error=str(e))
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid or expired token",
            )

    async def authenticate(self, websocket: WebSocket) -> WSTokenPayload:
        """Authenticate WebSocket connection.

        Returns token payload if valid, raises WebSocketException otherwise.
        """
        token = self.extract_token(websocket)

        if not token:
            logger.warning(
                "WebSocket connection without token",
                client=websocket.client.host if websocket.client else "unknown",
            )
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Authentication required",
            )

        payload = await self.validate_token(token)

        logger.info(
            "WebSocket authenticated",
            user_id=payload.sub,
            username=payload.preferred_username,
        )

        return payload


# Singleton instance
ws_authenticator = WebSocketAuthenticator()


async def authenticate_websocket(websocket: WebSocket) -> WSTokenPayload:
    """Authenticate WebSocket connection before accepting."""
    return await ws_authenticator.authenticate(websocket)
```

### Update WebSocket Endpoint

**File:** `src/realtime-streaming/api/v1/websocket.py` (MODIFY)

```python
# Add authentication to the WebSocket endpoint

from middleware.ws_auth import authenticate_websocket, WSTokenPayload

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint with authentication."""
    # Authenticate before accepting connection
    try:
        user = await authenticate_websocket(websocket)
    except WebSocketException as e:
        await websocket.close(code=e.code, reason=e.reason)
        return

    # Accept connection after successful authentication
    await websocket.accept()

    # Store user context for authorization checks
    websocket.state.user_id = user.sub
    websocket.state.username = user.preferred_username
    websocket.state.groups = user.groups

    # ... rest of the handler
```

### Tests

**File:** `src/realtime-streaming/tests/test_ws_auth.py`

```python
"""Tests for WebSocket authentication."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocketException
import time

from middleware.ws_auth import WebSocketAuthenticator, WSTokenPayload


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
```

---

## Task 1.4: Integration with FastAPI Application

**File:** `src/api-gateway/main.py` (MODIFY existing)

### Add Middleware Registration

```python
# Add to imports
from middleware.oauth import oauth_middleware, get_current_user
from services.rbac import get_user_context, require_permission, Permission

# Add after app initialization
from starlette.middleware.base import BaseHTTPMiddleware

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Global authentication middleware."""

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for certain paths
        skip_paths = ["/health", "/ready", "/metrics", "/docs", "/openapi.json"]

        if request.url.path in skip_paths:
            return await call_next(request)

        try:
            await oauth_middleware(request)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
            )

        return await call_next(request)


# Register middleware
app.add_middleware(AuthenticationMiddleware)
```

### Update Route Dependencies

**File:** Example route update in `src/api-gateway/api/v1/clusters.py`

```python
from fastapi import APIRouter, Depends
from services.rbac import (
    UserContext,
    get_user_context,
    require_permission,
    Permission,
)

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("/")
async def list_clusters(
    user: UserContext = Depends(get_user_context),
):
    """List all clusters (requires cluster:read permission)."""
    # Permission already checked by get_user_context
    # Access user.role, user.permissions as needed
    pass


@router.post("/")
async def create_cluster(
    user: UserContext = Depends(require_permission(Permission.CLUSTER_WRITE)),
):
    """Create a cluster (requires cluster:write permission)."""
    pass


@router.delete("/{cluster_id}")
async def delete_cluster(
    cluster_id: str,
    user: UserContext = Depends(require_permission(Permission.CLUSTER_DELETE)),
):
    """Delete a cluster (requires cluster:delete permission - admin only)."""
    pass
```

---

## Configuration Updates

**File:** `.env.example` (UPDATE)

```bash
# OAuth Configuration
OAUTH_ISSUER=https://oauth-openshift.apps.cluster.example.com
OAUTH_CLIENT_ID=aiops-nextgen
OAUTH_CLIENT_SECRET=your-client-secret-here

# Redis for session storage
REDIS_HOST=localhost
REDIS_PORT=6379
```

**File:** `src/shared/config/settings.py` (VERIFY existing OAuthSettings)

Already implemented correctly. No changes needed.

---

## Acceptance Criteria

- [ ] OAuth middleware validates JWT tokens from OpenShift
- [ ] Invalid/expired tokens return 401 Unauthorized
- [ ] JWKS is cached with 1-hour TTL
- [ ] RBAC service resolves roles from OpenShift groups
- [ ] Permission checks enforce access control on all endpoints
- [ ] Admin has all permissions, operator has read/write, viewer has read-only
- [ ] WebSocket connections require valid token before acceptance
- [ ] Token can be passed via query param or Sec-WebSocket-Protocol header
- [ ] Health/metrics endpoints bypass authentication
- [ ] All tests pass with >80% coverage

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/api-gateway/middleware/oauth.py` | CREATE | OAuth authentication middleware |
| `src/api-gateway/middleware/__init__.py` | CREATE | Middleware package init |
| `src/api-gateway/services/rbac.py` | CREATE | RBAC authorization service |
| `src/api-gateway/tests/test_oauth.py` | CREATE | OAuth middleware tests |
| `src/api-gateway/tests/test_rbac.py` | CREATE | RBAC service tests |
| `src/api-gateway/main.py` | MODIFY | Register auth middleware |
| `src/api-gateway/api/v1/*.py` | MODIFY | Add permission dependencies |
| `src/realtime-streaming/middleware/ws_auth.py` | CREATE | WebSocket auth middleware |
| `src/realtime-streaming/middleware/__init__.py` | CREATE | Middleware package init |
| `src/realtime-streaming/tests/test_ws_auth.py` | CREATE | WebSocket auth tests |
| `src/realtime-streaming/api/v1/websocket.py` | MODIFY | Add auth to WS endpoint |

---

## Dependencies

### Python packages (add to pyproject.toml)

```toml
dependencies = [
    # ... existing
    "python-jose[cryptography]>=3.3.0",  # JWT handling
    "httpx>=0.25.0",  # Async HTTP client for JWKS
]
```

---

## Rollback Plan

If issues arise:
1. Remove `AuthenticationMiddleware` from `main.py`
2. Remove `Depends()` from route handlers
3. Keep middleware files but don't import them
4. Set `OAUTH_ISSUER=""` to disable OAuth checks
