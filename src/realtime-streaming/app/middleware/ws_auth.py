"""WebSocket Authentication Middleware.

Spec Reference: specs/05-realtime-streaming.md Section 4
"""

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
        self._jwks_cache: dict | None = None

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

    def extract_token(self, websocket: WebSocket) -> str | None:
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
            ) from e

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
