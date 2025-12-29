"""OAuth 2.0 Authentication Middleware.

Spec Reference: specs/06-api-gateway.md Section 3.1
"""

import time

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
    email: str | None = None
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
        self._jwks_cache: dict | None = None
        self._jwks_cache_time: float = 0
        self._jwks_cache_ttl: int = 3600  # 1 hour
        self._config_cache: OAuthConfig | None = None

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
                ) from e

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
                ) from e

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
            ) from e

    async def __call__(self, request: Request) -> TokenPayload | None:
        """Extract and validate token from request."""
        # Skip auth for health endpoints
        if request.url.path in ["/health", "/ready", "/metrics"]:
            return None

        # Get authorization header
        auth: HTTPAuthorizationCredentials | None = await security(request)

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
