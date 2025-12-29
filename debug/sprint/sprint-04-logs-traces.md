# Sprint 4: Logs & Traces Collection

**Issues Addressed:** ISSUE-005 (HIGH), ISSUE-006 (HIGH)
**Priority:** P1
**Dependencies:** Sprint 1, Sprint 2, Sprint 3

---

## Overview

This sprint implements Loki (logs) and Tempo (traces) collectors. Currently only Prometheus is supported. The log and trace collection follows the same authentication and caching patterns established in Sprint 3.

---

## Task 4.1: Loki Log Client

**File:** `src/observability-collector/clients/loki.py`

### Implementation

```python
"""Loki Log Query Client.

Spec Reference: specs/03-observability-collector.md Section 3.2

Supports:
- LogQL queries
- Log streaming
- Label queries
- Authentication via Bearer token
"""

from datetime import datetime, timezone
from typing import Optional, AsyncIterator
from enum import Enum

import httpx
from pydantic import BaseModel

from shared.models import LogEntry, LogQuery, LogDirection
from shared.observability import get_logger

logger = get_logger(__name__)


class LokiAuthConfig(BaseModel):
    """Loki authentication configuration."""

    token: Optional[str] = None
    skip_tls_verify: bool = False


class LokiQueryResult(BaseModel):
    """Loki query result."""

    status: str
    entries: list[LogEntry]
    stats: Optional[dict] = None


class LokiClient:
    """Authenticated Loki query client."""

    def __init__(
        self,
        base_url: str,
        auth_config: LokiAuthConfig,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_config = auth_config
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            verify = not self.auth_config.skip_tls_verify

            self._client = httpx.AsyncClient(
                verify=verify,
                timeout=self.timeout,
            )

        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Build authentication headers."""
        headers = {"Content-Type": "application/json"}

        if self.auth_config.token:
            headers["Authorization"] = f"Bearer {self.auth_config.token}"

        return headers

    async def query(self, log_query: LogQuery) -> LokiQueryResult:
        """Execute LogQL query.

        Args:
            log_query: Log query specification

        Returns:
            LokiQueryResult with log entries
        """
        client = await self._get_client()
        headers = self._get_headers()

        # Build query parameters
        params = {
            "query": log_query.query,
            "limit": log_query.limit or 100,
            "direction": log_query.direction.value if log_query.direction else "backward",
        }

        if log_query.start:
            params["start"] = str(int(log_query.start.timestamp() * 1e9))
        if log_query.end:
            params["end"] = str(int(log_query.end.timestamp() * 1e9))

        try:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/query_range",
                headers=headers,
                params=params,
            )

            if response.status_code == 401:
                logger.error("Loki authentication failed")
                return LokiQueryResult(status="error", entries=[])

            if response.status_code == 403:
                logger.error("Loki authorization failed")
                return LokiQueryResult(status="error", entries=[])

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                return LokiQueryResult(
                    status="error",
                    entries=[],
                )

            entries = self._parse_log_entries(data)

            return LokiQueryResult(
                status="success",
                entries=entries,
                stats=data.get("data", {}).get("stats"),
            )

        except httpx.HTTPError as e:
            logger.error("Loki query failed", error=str(e))
            return LokiQueryResult(status="error", entries=[])

    async def query_instant(self, logql: str, limit: int = 100) -> LokiQueryResult:
        """Execute instant LogQL query.

        Args:
            logql: LogQL query string
            limit: Maximum number of entries

        Returns:
            LokiQueryResult with log entries
        """
        client = await self._get_client()
        headers = self._get_headers()

        params = {
            "query": logql,
            "limit": limit,
        }

        try:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/query",
                headers=headers,
                params=params,
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                return LokiQueryResult(status="error", entries=[])

            entries = self._parse_log_entries(data)

            return LokiQueryResult(
                status="success",
                entries=entries,
            )

        except httpx.HTTPError as e:
            logger.error("Loki instant query failed", error=str(e))
            return LokiQueryResult(status="error", entries=[])

    async def get_labels(self) -> list[str]:
        """Get all label names.

        Returns:
            List of label names
        """
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/labels",
                headers=headers,
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data.get("data", [])

            return []

        except httpx.HTTPError:
            return []

    async def get_label_values(self, label: str) -> list[str]:
        """Get values for a specific label.

        Args:
            label: Label name

        Returns:
            List of label values
        """
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.get(
                f"{self.base_url}/loki/api/v1/label/{label}/values",
                headers=headers,
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return data.get("data", [])

            return []

        except httpx.HTTPError:
            return []

    async def tail(
        self,
        logql: str,
        delay_for: int = 0,
    ) -> AsyncIterator[LogEntry]:
        """Stream logs in real-time.

        Args:
            logql: LogQL query for filtering
            delay_for: Delay in seconds before starting

        Yields:
            LogEntry objects as they arrive
        """
        import json

        client = await self._get_client()
        headers = self._get_headers()

        params = {
            "query": logql,
            "delay_for": delay_for,
        }

        try:
            async with client.stream(
                "GET",
                f"{self.base_url}/loki/api/v1/tail",
                headers=headers,
                params=params,
                timeout=None,  # No timeout for streaming
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            for stream in data.get("streams", []):
                                labels = stream.get("stream", {})
                                for value in stream.get("values", []):
                                    yield LogEntry(
                                        timestamp=datetime.fromtimestamp(
                                            int(value[0]) / 1e9,
                                            tz=timezone.utc,
                                        ),
                                        line=value[1],
                                        labels=labels,
                                    )
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPError as e:
            logger.error("Loki tail failed", error=str(e))

    def _parse_log_entries(self, data: dict) -> list[LogEntry]:
        """Parse Loki API response to LogEntry list."""
        entries = []
        result = data.get("data", {}).get("result", [])

        for stream in result:
            labels = stream.get("stream", {})

            for value in stream.get("values", []):
                timestamp_ns = int(value[0])
                line = value[1]

                entries.append(
                    LogEntry(
                        timestamp=datetime.fromtimestamp(
                            timestamp_ns / 1e9,
                            tz=timezone.utc,
                        ),
                        line=line,
                        labels=labels,
                    )
                )

        # Sort by timestamp (newest first for backward direction)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries

    async def check_health(self) -> bool:
        """Check Loki health.

        Returns:
            True if healthy
        """
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.get(
                f"{self.base_url}/ready",
                headers=headers,
                timeout=5.0,
            )
            return response.status_code == 200

        except httpx.HTTPError:
            return False

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


async def create_loki_client(
    cluster_id: str,
    loki_url: str,
    token: str,
    skip_tls_verify: bool = False,
) -> LokiClient:
    """Create authenticated Loki client for a cluster."""
    auth_config = LokiAuthConfig(
        token=token,
        skip_tls_verify=skip_tls_verify,
    )

    logger.info(
        "Creating Loki client",
        cluster_id=cluster_id,
        url=loki_url,
    )

    return LokiClient(
        base_url=loki_url,
        auth_config=auth_config,
    )
```

---

## Task 4.2: Tempo Trace Client

**File:** `src/observability-collector/clients/tempo.py`

### Implementation

```python
"""Tempo Trace Query Client.

Spec Reference: specs/03-observability-collector.md Section 3.3

Supports:
- Trace lookup by ID
- TraceQL queries
- Search by tags
- Authentication via Bearer token
"""

from datetime import datetime, timezone
from typing import Optional
import base64

import httpx
from pydantic import BaseModel

from shared.models import Trace, Span, SpanStatus, SpanLog, TraceQuery
from shared.observability import get_logger

logger = get_logger(__name__)


class TempoAuthConfig(BaseModel):
    """Tempo authentication configuration."""

    token: Optional[str] = None
    skip_tls_verify: bool = False


class TempoSearchResult(BaseModel):
    """Tempo search result."""

    traces: list[dict]
    total: int


class TempoClient:
    """Authenticated Tempo query client."""

    def __init__(
        self,
        base_url: str,
        auth_config: TempoAuthConfig,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_config = auth_config
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            verify = not self.auth_config.skip_tls_verify

            self._client = httpx.AsyncClient(
                verify=verify,
                timeout=self.timeout,
            )

        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Build authentication headers."""
        headers = {"Accept": "application/json"}

        if self.auth_config.token:
            headers["Authorization"] = f"Bearer {self.auth_config.token}"

        return headers

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get trace by ID.

        Args:
            trace_id: Trace ID (hex string)

        Returns:
            Trace object or None if not found
        """
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.get(
                f"{self.base_url}/api/traces/{trace_id}",
                headers=headers,
            )

            if response.status_code == 404:
                return None

            if response.status_code == 401:
                logger.error("Tempo authentication failed")
                return None

            response.raise_for_status()
            data = response.json()

            return self._parse_trace(data, trace_id)

        except httpx.HTTPError as e:
            logger.error("Tempo trace lookup failed", trace_id=trace_id, error=str(e))
            return None

    async def search(self, query: TraceQuery) -> TempoSearchResult:
        """Search for traces.

        Args:
            query: Trace query specification

        Returns:
            TempoSearchResult with matching traces
        """
        client = await self._get_client()
        headers = self._get_headers()

        # Build search parameters
        params = {
            "limit": query.limit or 20,
        }

        if query.service_name:
            params["service.name"] = query.service_name
        if query.operation_name:
            params["name"] = query.operation_name
        if query.min_duration:
            params["minDuration"] = query.min_duration
        if query.max_duration:
            params["maxDuration"] = query.max_duration
        if query.start:
            params["start"] = str(int(query.start.timestamp()))
        if query.end:
            params["end"] = str(int(query.end.timestamp()))
        if query.tags:
            for key, value in query.tags.items():
                params[key] = value

        try:
            response = await client.get(
                f"{self.base_url}/api/search",
                headers=headers,
                params=params,
            )

            if response.status_code == 401:
                logger.error("Tempo authentication failed")
                return TempoSearchResult(traces=[], total=0)

            response.raise_for_status()
            data = response.json()

            traces = data.get("traces", [])

            return TempoSearchResult(
                traces=traces,
                total=len(traces),
            )

        except httpx.HTTPError as e:
            logger.error("Tempo search failed", error=str(e))
            return TempoSearchResult(traces=[], total=0)

    async def search_tags(self) -> list[str]:
        """Get available search tags.

        Returns:
            List of tag names
        """
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.get(
                f"{self.base_url}/api/search/tags",
                headers=headers,
            )

            response.raise_for_status()
            data = response.json()

            return data.get("tagNames", [])

        except httpx.HTTPError:
            return []

    async def search_tag_values(self, tag: str) -> list[str]:
        """Get values for a specific tag.

        Args:
            tag: Tag name

        Returns:
            List of tag values
        """
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.get(
                f"{self.base_url}/api/search/tag/{tag}/values",
                headers=headers,
            )

            response.raise_for_status()
            data = response.json()

            return data.get("tagValues", [])

        except httpx.HTTPError:
            return []

    def _parse_trace(self, data: dict, trace_id: str) -> Trace:
        """Parse Tempo trace response to Trace model."""
        batches = data.get("batches", [])
        spans = []

        for batch in batches:
            resource = batch.get("resource", {})
            resource_attrs = {}

            for attr in resource.get("attributes", []):
                key = attr.get("key", "")
                value = attr.get("value", {})
                resource_attrs[key] = (
                    value.get("stringValue")
                    or value.get("intValue")
                    or value.get("boolValue")
                )

            for scope_span in batch.get("scopeSpans", []):
                for span_data in scope_span.get("spans", []):
                    span = self._parse_span(span_data, resource_attrs)
                    spans.append(span)

        # Sort spans by start time
        spans.sort(key=lambda s: s.start_time)

        # Calculate trace duration
        if spans:
            start_time = min(s.start_time for s in spans)
            end_time = max(s.end_time for s in spans)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
        else:
            start_time = datetime.now(timezone.utc)
            duration_ms = 0

        return Trace(
            trace_id=trace_id,
            spans=spans,
            service_name=resource_attrs.get("service.name", "unknown"),
            duration_ms=duration_ms,
            start_time=start_time,
        )

    def _parse_span(self, span_data: dict, resource_attrs: dict) -> Span:
        """Parse span data to Span model."""
        # Decode span and trace IDs from base64
        span_id = base64.b64decode(span_data.get("spanId", "")).hex()
        parent_id = None
        if span_data.get("parentSpanId"):
            parent_id = base64.b64decode(span_data["parentSpanId"]).hex()

        # Parse timestamps (nanoseconds)
        start_ns = int(span_data.get("startTimeUnixNano", 0))
        end_ns = int(span_data.get("endTimeUnixNano", 0))

        start_time = datetime.fromtimestamp(start_ns / 1e9, tz=timezone.utc)
        end_time = datetime.fromtimestamp(end_ns / 1e9, tz=timezone.utc)
        duration_ms = int((end_ns - start_ns) / 1e6)

        # Parse attributes
        attributes = dict(resource_attrs)
        for attr in span_data.get("attributes", []):
            key = attr.get("key", "")
            value = attr.get("value", {})
            attributes[key] = (
                value.get("stringValue")
                or value.get("intValue")
                or value.get("boolValue")
            )

        # Parse status
        status_data = span_data.get("status", {})
        status_code = status_data.get("code", 0)
        status = SpanStatus.OK
        if status_code == 2:
            status = SpanStatus.ERROR

        # Parse logs/events
        logs = []
        for event in span_data.get("events", []):
            event_time_ns = int(event.get("timeUnixNano", 0))
            logs.append(
                SpanLog(
                    timestamp=datetime.fromtimestamp(event_time_ns / 1e9, tz=timezone.utc),
                    message=event.get("name", ""),
                    attributes={
                        attr.get("key", ""): attr.get("value", {}).get("stringValue", "")
                        for attr in event.get("attributes", [])
                    },
                )
            )

        return Span(
            span_id=span_id,
            parent_span_id=parent_id,
            operation_name=span_data.get("name", "unknown"),
            service_name=attributes.get("service.name", "unknown"),
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            status=status,
            attributes=attributes,
            logs=logs,
        )

    async def check_health(self) -> bool:
        """Check Tempo health.

        Returns:
            True if healthy
        """
        client = await self._get_client()
        headers = self._get_headers()

        try:
            response = await client.get(
                f"{self.base_url}/ready",
                headers=headers,
                timeout=5.0,
            )
            return response.status_code == 200

        except httpx.HTTPError:
            return False

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


async def create_tempo_client(
    cluster_id: str,
    tempo_url: str,
    token: str,
    skip_tls_verify: bool = False,
) -> TempoClient:
    """Create authenticated Tempo client for a cluster."""
    auth_config = TempoAuthConfig(
        token=token,
        skip_tls_verify=skip_tls_verify,
    )

    logger.info(
        "Creating Tempo client",
        cluster_id=cluster_id,
        url=tempo_url,
    )

    return TempoClient(
        base_url=tempo_url,
        auth_config=auth_config,
    )
```

---

## Task 4.3: Logs Collector Service

**File:** `src/observability-collector/services/logs_collector.py`

### Implementation

```python
"""Logs Collector Service.

Spec Reference: specs/03-observability-collector.md Section 3.2
"""

import asyncio
from typing import Optional, AsyncIterator

from clients.loki import LokiClient, create_loki_client, LokiQueryResult
from shared.models import LogQuery, LogEntry
from shared.observability import get_logger

logger = get_logger(__name__)


class LogsCollector:
    """Collects logs from Loki instances across clusters."""

    def __init__(self):
        self._clients: dict[str, LokiClient] = {}

    async def get_client(
        self,
        cluster_id: str,
        loki_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> LokiClient:
        """Get or create Loki client for cluster."""
        cache_key = f"{cluster_id}:{loki_url}"

        if cache_key not in self._clients:
            self._clients[cache_key] = await create_loki_client(
                cluster_id=cluster_id,
                loki_url=loki_url,
                token=token,
                skip_tls_verify=skip_tls_verify,
            )

        return self._clients[cache_key]

    async def query_logs(
        self,
        cluster_id: str,
        loki_url: str,
        token: str,
        query: LogQuery,
        skip_tls_verify: bool = False,
    ) -> LokiQueryResult:
        """Query logs from a cluster.

        Args:
            cluster_id: Cluster identifier
            loki_url: Loki URL
            token: Bearer token
            query: Log query specification
            skip_tls_verify: Skip TLS verification

        Returns:
            LokiQueryResult with log entries
        """
        client = await self.get_client(
            cluster_id, loki_url, token, skip_tls_verify
        )

        return await client.query(query)

    async def stream_logs(
        self,
        cluster_id: str,
        loki_url: str,
        token: str,
        logql: str,
        skip_tls_verify: bool = False,
    ) -> AsyncIterator[LogEntry]:
        """Stream logs in real-time.

        Args:
            cluster_id: Cluster identifier
            loki_url: Loki URL
            token: Bearer token
            logql: LogQL query for filtering
            skip_tls_verify: Skip TLS verification

        Yields:
            LogEntry objects as they arrive
        """
        client = await self.get_client(
            cluster_id, loki_url, token, skip_tls_verify
        )

        async for entry in client.tail(logql):
            yield entry

    async def get_labels(
        self,
        cluster_id: str,
        loki_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> list[str]:
        """Get available log labels for a cluster."""
        client = await self.get_client(
            cluster_id, loki_url, token, skip_tls_verify
        )

        return await client.get_labels()

    async def close(self):
        """Close all clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


# Singleton instance
logs_collector = LogsCollector()
```

---

## Task 4.4: Traces Collector Service

**File:** `src/observability-collector/services/traces_collector.py`

### Implementation

```python
"""Traces Collector Service.

Spec Reference: specs/03-observability-collector.md Section 3.3
"""

from typing import Optional

from clients.tempo import TempoClient, create_tempo_client, TempoSearchResult
from shared.models import Trace, TraceQuery
from shared.observability import get_logger

logger = get_logger(__name__)


class TracesCollector:
    """Collects traces from Tempo instances across clusters."""

    def __init__(self):
        self._clients: dict[str, TempoClient] = {}

    async def get_client(
        self,
        cluster_id: str,
        tempo_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> TempoClient:
        """Get or create Tempo client for cluster."""
        cache_key = f"{cluster_id}:{tempo_url}"

        if cache_key not in self._clients:
            self._clients[cache_key] = await create_tempo_client(
                cluster_id=cluster_id,
                tempo_url=tempo_url,
                token=token,
                skip_tls_verify=skip_tls_verify,
            )

        return self._clients[cache_key]

    async def get_trace(
        self,
        cluster_id: str,
        tempo_url: str,
        token: str,
        trace_id: str,
        skip_tls_verify: bool = False,
    ) -> Optional[Trace]:
        """Get a specific trace by ID.

        Args:
            cluster_id: Cluster identifier
            tempo_url: Tempo URL
            token: Bearer token
            trace_id: Trace ID to retrieve
            skip_tls_verify: Skip TLS verification

        Returns:
            Trace object or None if not found
        """
        client = await self.get_client(
            cluster_id, tempo_url, token, skip_tls_verify
        )

        return await client.get_trace(trace_id)

    async def search_traces(
        self,
        cluster_id: str,
        tempo_url: str,
        token: str,
        query: TraceQuery,
        skip_tls_verify: bool = False,
    ) -> TempoSearchResult:
        """Search for traces.

        Args:
            cluster_id: Cluster identifier
            tempo_url: Tempo URL
            token: Bearer token
            query: Trace query specification
            skip_tls_verify: Skip TLS verification

        Returns:
            TempoSearchResult with matching traces
        """
        client = await self.get_client(
            cluster_id, tempo_url, token, skip_tls_verify
        )

        return await client.search(query)

    async def get_available_services(
        self,
        cluster_id: str,
        tempo_url: str,
        token: str,
        skip_tls_verify: bool = False,
    ) -> list[str]:
        """Get list of services with traces.

        Args:
            cluster_id: Cluster identifier
            tempo_url: Tempo URL
            token: Bearer token
            skip_tls_verify: Skip TLS verification

        Returns:
            List of service names
        """
        client = await self.get_client(
            cluster_id, tempo_url, token, skip_tls_verify
        )

        return await client.search_tag_values("service.name")

    async def close(self):
        """Close all clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


# Singleton instance
traces_collector = TracesCollector()
```

---

## Task 4.5: API Endpoints

**File:** `src/observability-collector/api/v1/logs.py`

```python
"""Logs API endpoints.

Spec Reference: specs/03-observability-collector.md Section 5.2
"""

from fastapi import APIRouter, HTTPException, status

from services.logs_collector import logs_collector
from services.cluster_client import get_cluster_credentials
from shared.models import LogQuery, LogEntry
from clients.loki import LokiQueryResult

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/query")
async def query_logs(
    cluster_id: str,
    query: LogQuery,
) -> LokiQueryResult:
    """Query logs from cluster Loki."""
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    if not cluster.endpoints.loki_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cluster {cluster_id} does not have Loki configured",
        )

    return await logs_collector.query_logs(
        cluster_id=cluster_id,
        loki_url=cluster.endpoints.loki_url,
        token=cluster.credentials.token,
        query=query,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )


@router.get("/labels")
async def get_log_labels(cluster_id: str) -> list[str]:
    """Get available log labels for a cluster."""
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster or not cluster.endpoints.loki_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found or Loki not configured",
        )

    return await logs_collector.get_labels(
        cluster_id=cluster_id,
        loki_url=cluster.endpoints.loki_url,
        token=cluster.credentials.token,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )
```

**File:** `src/observability-collector/api/v1/traces.py`

```python
"""Traces API endpoints.

Spec Reference: specs/03-observability-collector.md Section 5.3
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status

from services.traces_collector import traces_collector
from services.cluster_client import get_cluster_credentials
from shared.models import Trace, TraceQuery
from clients.tempo import TempoSearchResult

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("/{trace_id}")
async def get_trace(
    cluster_id: str,
    trace_id: str,
) -> Trace:
    """Get a specific trace by ID."""
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    if not cluster.endpoints.tempo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cluster {cluster_id} does not have Tempo configured",
        )

    trace = await traces_collector.get_trace(
        cluster_id=cluster_id,
        tempo_url=cluster.endpoints.tempo_url,
        token=cluster.credentials.token,
        trace_id=trace_id,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )

    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace {trace_id} not found",
        )

    return trace


@router.post("/search")
async def search_traces(
    cluster_id: str,
    query: TraceQuery,
) -> TempoSearchResult:
    """Search for traces."""
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    if not cluster.endpoints.tempo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cluster {cluster_id} does not have Tempo configured",
        )

    return await traces_collector.search_traces(
        cluster_id=cluster_id,
        tempo_url=cluster.endpoints.tempo_url,
        token=cluster.credentials.token,
        query=query,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )


@router.get("/services")
async def get_services(cluster_id: str) -> list[str]:
    """Get list of services with traces."""
    cluster = await get_cluster_credentials(cluster_id)

    if not cluster or not cluster.endpoints.tempo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found or Tempo not configured",
        )

    return await traces_collector.get_available_services(
        cluster_id=cluster_id,
        tempo_url=cluster.endpoints.tempo_url,
        token=cluster.credentials.token,
        skip_tls_verify=cluster.credentials.skip_tls_verify,
    )
```

---

## Acceptance Criteria

- [ ] Loki client executes LogQL queries with authentication
- [ ] Log entries parsed with timestamps, labels, and content
- [ ] Log streaming via tail endpoint works
- [ ] Tempo client retrieves traces by ID
- [ ] Trace search by service, operation, duration works
- [ ] Span hierarchy parsed correctly (parent/child)
- [ ] Span logs/events included in response
- [ ] Both clients handle 401/403 errors appropriately
- [ ] All tests pass with >80% coverage

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/observability-collector/clients/loki.py` | CREATE | Loki client |
| `src/observability-collector/clients/tempo.py` | CREATE | Tempo client |
| `src/observability-collector/services/logs_collector.py` | CREATE | Logs collector service |
| `src/observability-collector/services/traces_collector.py` | CREATE | Traces collector service |
| `src/observability-collector/api/v1/logs.py` | CREATE | Logs API endpoints |
| `src/observability-collector/api/v1/traces.py` | CREATE | Traces API endpoints |
| `src/observability-collector/tests/test_loki_client.py` | CREATE | Loki tests |
| `src/observability-collector/tests/test_tempo_client.py` | CREATE | Tempo tests |
