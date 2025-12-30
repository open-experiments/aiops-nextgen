"""Tempo collector for distributed trace queries.

Spec Reference: specs/03-observability-collector.md Section 4.2
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from shared.config import get_settings
from shared.observability import get_logger

logger = get_logger(__name__)


class TempoCollector:
    """Collector for Tempo/trace queries.

    Spec Reference: specs/03-observability-collector.md Section 4.2
    """

    def __init__(self):
        self.settings = get_settings()
        # Skip TLS verification in development mode
        verify = not self.settings.is_development
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=True,
            verify=verify,
        )

    async def search_traces(
        self,
        cluster: dict,
        service_name: str | None = None,
        operation: str | None = None,
        tags: dict[str, str] | None = None,
        min_duration: str | None = None,
        max_duration: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 20,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Search traces by criteria.

        Args:
            cluster: Cluster configuration with Tempo URL
            service_name: Filter by service name
            operation: Filter by operation/span name
            tags: Filter by span tags
            min_duration: Minimum trace duration (e.g., "100ms")
            max_duration: Maximum trace duration (e.g., "1s")
            start_time: Search start time
            end_time: Search end time
            limit: Maximum number of traces
            timeout: Query timeout

        Returns:
            Search results with trace summaries
        """
        tempo_url = cluster.get("endpoints", {}).get("tempo_url")

        if not tempo_url:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": "No Tempo URL configured",
                "traces": [],
            }

        # Build TraceQL query or use tags-based search
        url = f"{tempo_url}/api/search"
        params: dict[str, Any] = {"limit": limit}

        # Build tag-based query parameters
        if service_name:
            params["tags"] = f"service.name={service_name}"
        if tags:
            tag_str = " ".join(f"{k}={v}" for k, v in tags.items())
            if "tags" in params:
                params["tags"] += f" {tag_str}"
            else:
                params["tags"] = tag_str

        if min_duration:
            params["minDuration"] = min_duration
        if max_duration:
            params["maxDuration"] = max_duration
        if start_time:
            params["start"] = int(start_time.timestamp())
        if end_time:
            params["end"] = int(end_time.timestamp())

        try:
            headers = self._get_auth_headers(cluster)

            response = await asyncio.wait_for(
                self.client.get(url, params=params, headers=headers),
                timeout=timeout,
            )

            if response.status_code == 401:
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": "Authentication failed",
                    "traces": [],
                }

            if response.status_code != 200:
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "traces": [],
                }

            data = response.json()
            traces = data.get("traces", [])

            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "SUCCESS",
                "traces": [self._parse_trace_summary(t) for t in traces],
            }

        except TimeoutError:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "TIMEOUT",
                "error": f"Search timed out after {timeout}s",
                "traces": [],
            }
        except Exception as e:
            logger.error(
                "Tempo search failed",
                cluster_id=cluster["id"],
                error=str(e),
            )
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": str(e),
                "traces": [],
            }

    async def get_trace(
        self,
        cluster: dict,
        trace_id: str,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Get a specific trace by ID.

        Args:
            cluster: Cluster configuration
            trace_id: Trace ID to retrieve
            timeout: Query timeout

        Returns:
            Full trace with all spans
        """
        tempo_url = cluster.get("endpoints", {}).get("tempo_url")

        if not tempo_url:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": "No Tempo URL configured",
                "trace": None,
            }

        url = f"{tempo_url}/api/traces/{trace_id}"

        try:
            headers = self._get_auth_headers(cluster)

            response = await asyncio.wait_for(
                self.client.get(url, headers=headers),
                timeout=timeout,
            )

            if response.status_code == 404:
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "NOT_FOUND",
                    "error": f"Trace {trace_id} not found",
                    "trace": None,
                }

            if response.status_code != 200:
                return {
                    "cluster_id": str(cluster["id"]),
                    "cluster_name": cluster["name"],
                    "status": "ERROR",
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                    "trace": None,
                }

            data = response.json()

            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "SUCCESS",
                "trace": self._parse_trace(data, trace_id),
            }

        except TimeoutError:
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "TIMEOUT",
                "error": f"Get trace timed out after {timeout}s",
                "trace": None,
            }
        except Exception as e:
            logger.error(
                "Tempo get trace failed",
                cluster_id=cluster["id"],
                trace_id=trace_id,
                error=str(e),
            )
            return {
                "cluster_id": str(cluster["id"]),
                "cluster_name": cluster["name"],
                "status": "ERROR",
                "error": str(e),
                "trace": None,
            }

    async def get_services(self, cluster: dict) -> list[str]:
        """Get list of services with traces.

        Args:
            cluster: Cluster configuration

        Returns:
            List of service names
        """
        tempo_url = cluster.get("endpoints", {}).get("tempo_url")

        if not tempo_url:
            return []

        # Tempo uses tag values API
        url = f"{tempo_url}/api/search/tag/service.name/values"

        try:
            headers = self._get_auth_headers(cluster)
            response = await self.client.get(url, headers=headers)

            if response.status_code != 200:
                return []

            data = response.json()
            return data.get("tagValues", [])

        except Exception as e:
            logger.warning(
                "Failed to get Tempo services",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return []

    async def get_operations(self, cluster: dict, service: str) -> list[str]:
        """Get operations/span names for a service.

        Args:
            cluster: Cluster configuration
            service: Service name

        Returns:
            List of operation names
        """
        tempo_url = cluster.get("endpoints", {}).get("tempo_url")

        if not tempo_url:
            return []

        url = f"{tempo_url}/api/search/tag/name/values"
        params = {"tags": f"service.name={service}"}

        try:
            headers = self._get_auth_headers(cluster)
            response = await self.client.get(url, params=params, headers=headers)

            if response.status_code != 200:
                return []

            data = response.json()
            return data.get("tagValues", [])

        except Exception as e:
            logger.warning(
                "Failed to get Tempo operations",
                cluster_id=cluster.get("id"),
                service=service,
                error=str(e),
            )
            return []

    async def get_service_graph(
        self,
        cluster: dict,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get service dependency graph.

        Args:
            cluster: Cluster configuration
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            Service dependency graph with nodes and edges
        """
        tempo_url = cluster.get("endpoints", {}).get("tempo_url")

        if not tempo_url:
            return {"nodes": [], "edges": []}

        # Try metrics generator endpoint if available
        url = f"{tempo_url}/api/metrics/query_range"
        params: dict[str, Any] = {
            "query": "traces_service_graph_request_total",
        }

        if start_time:
            params["start"] = int(start_time.timestamp())
        if end_time:
            params["end"] = int(end_time.timestamp())

        try:
            headers = self._get_auth_headers(cluster)
            response = await self.client.get(url, params=params, headers=headers)

            if response.status_code != 200:
                # Fall back to building graph from traces
                return await self._build_graph_from_traces(cluster)

            data = response.json()
            return self._parse_service_graph(data)

        except Exception as e:
            logger.warning(
                "Failed to get Tempo service graph",
                cluster_id=cluster.get("id"),
                error=str(e),
            )
            return {"nodes": [], "edges": []}

    async def _build_graph_from_traces(self, cluster: dict) -> dict[str, Any]:
        """Build service graph from sampled traces."""
        # Search for recent traces
        result = await self.search_traces(cluster, limit=100)

        if result["status"] != "SUCCESS":
            return {"nodes": [], "edges": []}

        services: set[str] = set()
        edges: dict[tuple[str, str], int] = {}

        for trace_summary in result.get("traces", []):
            # Get full trace to analyze spans
            trace_id = trace_summary.get("traceID")
            if not trace_id:
                continue

            trace_result = await self.get_trace(cluster, trace_id)
            if trace_result["status"] != "SUCCESS":
                continue

            trace = trace_result.get("trace", {})
            spans = trace.get("spans", [])

            # Build edges from parent-child relationships
            span_map = {s["spanID"]: s for s in spans}
            for span in spans:
                service = span.get("serviceName", "unknown")
                services.add(service)

                parent_id = span.get("parentSpanID")
                if parent_id and parent_id in span_map:
                    parent_service = span_map[parent_id].get("serviceName", "unknown")
                    if parent_service != service:
                        edge = (parent_service, service)
                        edges[edge] = edges.get(edge, 0) + 1

        return {
            "nodes": [{"id": s, "label": s} for s in services],
            "edges": [
                {"source": src, "target": tgt, "weight": count}
                for (src, tgt), count in edges.items()
            ],
        }

    def _get_auth_headers(self, cluster: dict) -> dict[str, str]:
        """Get authentication headers for cluster."""
        headers = {}

        credentials = cluster.get("credentials", {})
        token = credentials.get("token")

        # For development, use pod's service account token
        if not token and self.settings.is_development:
            try:
                with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                    token = f.read().strip()
            except FileNotFoundError:
                pass

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _parse_trace_summary(self, trace: dict) -> dict:
        """Parse trace summary from search results."""
        return {
            "traceID": trace.get("traceID", ""),
            "rootServiceName": trace.get("rootServiceName", ""),
            "rootTraceName": trace.get("rootTraceName", ""),
            "startTimeUnixNano": trace.get("startTimeUnixNano", 0),
            "durationMs": trace.get("durationMs", 0),
            "spanCount": len(trace.get("spanSets", [{}])[0].get("spans", [])),
        }

    def _parse_trace(self, data: dict, trace_id: str) -> dict:
        """Parse full trace from Tempo response."""
        # Tempo returns OTLP format
        batches = data.get("batches", [])
        spans = []

        for batch in batches:
            resource = batch.get("resource", {})
            resource_attrs = self._parse_attributes(resource.get("attributes", []))
            service_name = resource_attrs.get("service.name", "unknown")

            scope_spans = batch.get("scopeSpans", [])
            for scope_span in scope_spans:
                for span in scope_span.get("spans", []):
                    spans.append(
                        {
                            "traceID": trace_id,
                            "spanID": span.get("spanId", ""),
                            "parentSpanID": span.get("parentSpanId", ""),
                            "operationName": span.get("name", ""),
                            "serviceName": service_name,
                            "startTime": span.get("startTimeUnixNano", 0),
                            "duration": (
                                span.get("endTimeUnixNano", 0) - span.get("startTimeUnixNano", 0)
                            ),
                            "status": span.get("status", {}).get("code", "UNSET"),
                            "tags": self._parse_attributes(span.get("attributes", [])),
                            "events": [
                                {
                                    "name": e.get("name", ""),
                                    "timestamp": e.get("timeUnixNano", 0),
                                    "attributes": self._parse_attributes(e.get("attributes", [])),
                                }
                                for e in span.get("events", [])
                            ],
                        }
                    )

        return {
            "traceID": trace_id,
            "spans": spans,
            "spanCount": len(spans),
            "services": list({s["serviceName"] for s in spans}),
        }

    def _parse_attributes(self, attributes: list) -> dict:
        """Parse OTLP attributes to dict."""
        result = {}
        for attr in attributes:
            key = attr.get("key", "")
            value = attr.get("value", {})
            # Handle different value types
            if "stringValue" in value:
                result[key] = value["stringValue"]
            elif "intValue" in value:
                result[key] = int(value["intValue"])
            elif "boolValue" in value:
                result[key] = value["boolValue"]
            elif "doubleValue" in value:
                result[key] = value["doubleValue"]
        return result

    def _parse_service_graph(self, data: dict) -> dict[str, Any]:
        """Parse service graph from metrics data."""
        nodes: set[str] = set()
        edges: dict[tuple[str, str], int] = {}

        result = data.get("data", {}).get("result", [])
        for series in result:
            metric = series.get("metric", {})
            client = metric.get("client", "")
            server = metric.get("server", "")

            if client:
                nodes.add(client)
            if server:
                nodes.add(server)
            if client and server:
                edge = (client, server)
                values = series.get("values", [])
                if values:
                    edges[edge] = int(float(values[-1][1]))

        return {
            "nodes": [{"id": n, "label": n} for n in nodes],
            "edges": [
                {"source": src, "target": tgt, "weight": count}
                for (src, tgt), count in edges.items()
            ],
        }

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
