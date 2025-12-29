"""Tests for Real-Time Streaming service."""

import pytest
from app.services.hub import WebSocketHub
from app.services.subscriptions import SubscriptionManager


class TestWebSocketHub:
    """Tests for WebSocketHub."""

    @pytest.mark.asyncio
    async def test_client_count_starts_at_zero(self):
        hub = WebSocketHub()
        assert hub.get_client_count() == 0

    @pytest.mark.asyncio
    async def test_is_connected_false_for_unknown_client(self):
        hub = WebSocketHub()
        assert hub.is_connected("unknown") is False


class TestSubscriptionManager:
    """Tests for SubscriptionManager."""

    @pytest.mark.asyncio
    async def test_subscribe_and_match(self):
        manager = SubscriptionManager()

        await manager.subscribe(
            "client-1",
            event_types=["ALERT_FIRED", "GPU_UPDATE"],
        )

        # Event should match
        event = {"event_type": "ALERT_FIRED", "cluster_id": None}
        clients = await manager.match_event(event)
        assert "client-1" in clients

        # Non-subscribed event should not match
        event = {"event_type": "CLUSTER_DELETED", "cluster_id": None}
        clients = await manager.match_event(event)
        assert "client-1" not in clients

    @pytest.mark.asyncio
    async def test_unsubscribe_all(self):
        manager = SubscriptionManager()

        await manager.subscribe(
            "client-1",
            event_types=["ALERT_FIRED"],
        )

        await manager.unsubscribe("client-1")

        sub = await manager.get_subscriptions("client-1")
        assert sub is None

    @pytest.mark.asyncio
    async def test_invalid_event_type_ignored(self):
        manager = SubscriptionManager()

        await manager.subscribe(
            "client-1",
            event_types=["INVALID_TYPE", "ALERT_FIRED"],
        )

        sub = await manager.get_subscriptions("client-1")
        assert "ALERT_FIRED" in sub.event_types
        assert "INVALID_TYPE" not in sub.event_types

    @pytest.mark.asyncio
    async def test_cluster_filter(self):
        manager = SubscriptionManager()

        await manager.subscribe(
            "client-1",
            event_types=["ALERT_FIRED"],
            cluster_filter=["cluster-abc"],
        )

        # Matching cluster
        event = {"event_type": "ALERT_FIRED", "cluster_id": "cluster-abc"}
        clients = await manager.match_event(event)
        assert "client-1" in clients

        # Non-matching cluster
        event = {"event_type": "ALERT_FIRED", "cluster_id": "cluster-xyz"}
        clients = await manager.match_event(event)
        assert "client-1" not in clients
