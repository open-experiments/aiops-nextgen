"""WebSocket Proxy for API Gateway.

Spec Reference: specs/06-api-gateway.md Section 4.3

Proxies WebSocket connections to the realtime-streaming service
while maintaining authentication context.
"""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from shared.config import get_settings
from shared.observability import get_logger

from ..middleware.oauth import oauth_middleware

logger = get_logger(__name__)
router = APIRouter()


class WebSocketProxy:
    """Proxies WebSocket connections to backend service."""

    def __init__(self):
        """Initialize the WebSocket proxy."""
        self.settings = get_settings()
        self._backend_url: str | None = None

    @property
    def backend_url(self) -> str:
        """Get backend WebSocket URL."""
        if self._backend_url is None:
            http_url = getattr(
                self.settings.services, "realtime_streaming_url",
                "http://realtime-streaming:8080"
            )
            self._backend_url = http_url.replace(
                "http://", "ws://"
            ).replace("https://", "wss://")
        return self._backend_url

    def extract_token(self, websocket: WebSocket) -> str | None:
        """Extract authentication token from WebSocket connection.

        Token can be provided via:
        1. Query parameter: ?token=xxx
        2. Sec-WebSocket-Protocol header: bearer, <token>

        Args:
            websocket: The WebSocket connection

        Returns:
            Token string or None if not found
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

    async def proxy(self, client_ws: WebSocket) -> None:
        """Proxy a WebSocket connection to the backend.

        Args:
            client_ws: Client WebSocket connection
        """
        settings = get_settings()

        # Skip authentication if OAuth is not configured (development mode)
        if settings.oauth.issuer:
            # Authenticate the client via OAuth
            try:
                # Create a mock request for OAuth middleware
                # Note: WebSocket doesn't have a standard auth header,
                # so we extract token from query params or protocol header
                token = self.extract_token(client_ws)
                if not token:
                    logger.warning("WebSocket proxy auth failed: no token")
                    await client_ws.close(code=1008, reason="Authentication required")
                    return

                # Validate the token using OAuth middleware
                await oauth_middleware.validate_token(token)

            except Exception as e:
                logger.warning("WebSocket proxy auth failed", error=str(e))
                await client_ws.close(code=1008, reason="Authentication failed")
                return

        # Accept client connection
        await client_ws.accept()

        # Extract token to forward to backend
        token = self.extract_token(client_ws)
        backend_url = f"{self.backend_url}/ws"
        if token:
            backend_url = f"{backend_url}?token={token}"

        logger.info(
            "Proxying WebSocket connection",
            backend_url=self.backend_url,
            client=client_ws.client.host if client_ws.client else "unknown",
        )

        try:
            # Import websockets for backend connection
            # Note: websockets library provides proper WebSocket client support
            import websockets

            async with websockets.connect(
                backend_url,
                ping_interval=None,  # Let backend handle pings
                ping_timeout=None,
            ) as backend_ws:
                # Start bidirectional proxy
                await asyncio.gather(
                    self._forward_client_to_backend(client_ws, backend_ws),
                    self._forward_backend_to_client(backend_ws, client_ws),
                    return_exceptions=True,
                )

        except ImportError:
            # websockets library not available, use simplified approach
            logger.warning("websockets library not available, using direct pass-through")
            await self._simple_proxy(client_ws, backend_url)

        except Exception as e:
            logger.error("WebSocket proxy error", error=str(e))
            if client_ws.client_state == WebSocketState.CONNECTED:
                await client_ws.close(code=1011, reason="Backend unavailable")

    async def _forward_client_to_backend(
        self, client_ws: WebSocket, backend_ws
    ) -> None:
        """Forward messages from client to backend.

        Args:
            client_ws: Client WebSocket connection
            backend_ws: Backend WebSocket connection
        """
        try:
            while True:
                data = await client_ws.receive_text()
                await backend_ws.send(data)
        except WebSocketDisconnect:
            await backend_ws.close()
        except Exception as e:
            logger.debug("Client to backend forward ended", reason=str(e))

    async def _forward_backend_to_client(
        self, backend_ws, client_ws: WebSocket
    ) -> None:
        """Forward messages from backend to client.

        Args:
            backend_ws: Backend WebSocket connection
            client_ws: Client WebSocket connection
        """
        try:
            async for message in backend_ws:
                if client_ws.client_state == WebSocketState.CONNECTED:
                    await client_ws.send_text(message)
                else:
                    break
        except Exception as e:
            logger.debug("Backend to client forward ended", reason=str(e))
            if client_ws.client_state == WebSocketState.CONNECTED:
                await client_ws.close()

    async def _simple_proxy(self, client_ws: WebSocket, backend_url: str) -> None:
        """Simple proxy when websockets library is not available.

        This is a fallback that just relays messages without proper
        bidirectional support.

        Args:
            client_ws: Client WebSocket connection
            backend_url: Backend WebSocket URL
        """
        # Without websockets library, we can't properly connect to backend
        # Just acknowledge the connection and let client know
        await client_ws.send_json({
            "type": "error",
            "code": "PROXY_UNAVAILABLE",
            "message": "WebSocket proxy not available. Connect directly to realtime-streaming.",
        })
        await client_ws.close(code=1011, reason="Proxy not configured")


# Singleton instance
ws_proxy = WebSocketProxy()


@router.websocket("/ws")
async def websocket_proxy_endpoint(websocket: WebSocket):
    """WebSocket proxy endpoint.

    Proxies WebSocket connections from clients to the realtime-streaming
    service, handling authentication at the gateway level.

    Spec Reference: specs/06-api-gateway.md Section 4.3
    """
    await ws_proxy.proxy(websocket)


@router.websocket("/api/v1/ws")
async def websocket_proxy_v1_endpoint(websocket: WebSocket):
    """WebSocket proxy endpoint (v1 API path).

    Alias for /ws under the API version prefix.
    """
    await ws_proxy.proxy(websocket)
