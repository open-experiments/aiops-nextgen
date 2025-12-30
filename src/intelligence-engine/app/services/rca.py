"""Root Cause Analysis Service.

Spec Reference: specs/04-intelligence-engine.md Section 5

Implements correlation-based root cause analysis:
- Temporal correlation of anomalies
- Metric correlation analysis
- Dependency graph traversal
- LLM-assisted explanation generation
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel

from shared.models import AnomalyDetection
from shared.observability import get_logger

logger = get_logger(__name__)


class CorrelatedAnomaly(BaseModel):
    """An anomaly correlated to a root cause."""

    anomaly: AnomalyDetection
    correlation_score: float
    time_lag_seconds: float
    relationship: str  # "caused_by", "correlated_with", "symptom_of"


class RootCause(BaseModel):
    """Identified root cause."""

    id: str
    cluster_id: str
    identified_at: datetime
    confidence: float
    primary_anomaly: AnomalyDetection
    correlated_anomalies: list[CorrelatedAnomaly]
    probable_cause: str
    recommended_actions: list[str]
    evidence: dict


class RCAConfig(BaseModel):
    """Configuration for root cause analysis."""

    time_window_minutes: int = 30
    correlation_threshold: float = 0.7
    max_time_lag_seconds: float = 300
    min_anomalies_for_rca: int = 2


class RootCauseAnalyzer:
    """Root cause analysis engine."""

    def __init__(self, config: RCAConfig | None = None):
        """Initialize the RCA analyzer.

        Args:
            config: RCA configuration
        """
        self.config = config or RCAConfig()

        # Known dependency patterns
        self._dependencies: dict[str, list[str]] = {
            "container_cpu_usage": ["node_cpu_usage"],
            "container_memory_usage": ["node_memory_usage"],
            "pod_restarts": ["container_oom_kills", "node_memory_pressure"],
            "http_request_latency": ["database_query_time", "network_latency"],
            "http_5xx_errors": ["pod_restarts", "container_cpu_throttling"],
            "gpu_memory_usage": ["gpu_utilization"],
            "gpu_temperature": ["gpu_utilization", "gpu_power_usage"],
        }

        # Metric to component mapping
        self._metric_components: dict[str, str] = {
            "node_cpu_usage": "node",
            "node_memory_usage": "node",
            "container_cpu_usage": "container",
            "container_memory_usage": "container",
            "pod_restarts": "pod",
            "http_request_latency": "service",
            "gpu_utilization": "gpu",
            "gpu_memory_usage": "gpu",
        }

    async def analyze(
        self,
        anomalies: list[AnomalyDetection],
    ) -> list[RootCause]:
        """Analyze anomalies to identify root causes.

        Args:
            anomalies: List of detected anomalies

        Returns:
            List of identified root causes
        """
        if len(anomalies) < self.config.min_anomalies_for_rca:
            return []

        # Group anomalies by cluster
        by_cluster: dict[str, list[AnomalyDetection]] = defaultdict(list)
        for anomaly in anomalies:
            by_cluster[str(anomaly.cluster_id)].append(anomaly)

        root_causes = []

        for _cluster_id, cluster_anomalies in by_cluster.items():
            # Sort by time
            sorted_anomalies = sorted(cluster_anomalies, key=lambda a: a.detected_at)

            # Find temporal correlations
            correlations = self._find_temporal_correlations(sorted_anomalies)

            # Find metric correlations
            metric_correlations = self._find_metric_correlations(sorted_anomalies)

            # Identify root causes
            causes = self._identify_root_causes(
                sorted_anomalies,
                correlations,
                metric_correlations,
            )

            root_causes.extend(causes)

        return root_causes

    def _find_temporal_correlations(
        self,
        anomalies: list[AnomalyDetection],
    ) -> dict[str, list[tuple[AnomalyDetection, float]]]:
        """Find temporally correlated anomalies.

        Returns dict mapping anomaly ID to list of (correlated_anomaly, time_lag).
        """
        correlations: dict[str, list[tuple[AnomalyDetection, float]]] = defaultdict(list)
        max_lag = self.config.max_time_lag_seconds

        for i, anomaly in enumerate(anomalies):
            for j, other in enumerate(anomalies):
                if i == j:
                    continue

                time_diff = (other.detected_at - anomaly.detected_at).total_seconds()

                # Look for anomalies that occurred after this one (effects)
                if 0 < time_diff <= max_lag:
                    correlations[str(anomaly.id)].append((other, time_diff))

        return correlations

    def _find_metric_correlations(
        self,
        anomalies: list[AnomalyDetection],
    ) -> dict[str, list[tuple[str, float]]]:
        """Find correlations based on known metric dependencies.

        Returns dict mapping anomaly ID to list of (correlated_anomaly_id, score).
        """
        correlations: dict[str, list[tuple[str, float]]] = defaultdict(list)

        for anomaly in anomalies:
            # Check if this metric is a known effect of other metrics
            for dep_metric, effects in self._dependencies.items():
                if anomaly.metric_name in effects or self._metric_matches(
                    anomaly.metric_name, effects
                ):
                    # Look for anomalies in the dependency metric
                    for other in anomalies:
                        if self._metric_matches(other.metric_name, [dep_metric]) and str(
                            other.id
                        ) != str(anomaly.id):
                            # Calculate correlation score based on severity
                            score = self._calculate_correlation_score(anomaly, other)
                            if score >= self.config.correlation_threshold:
                                correlations[str(anomaly.id)].append((str(other.id), score))

        return correlations

    def _metric_matches(self, metric_name: str, patterns: list[str]) -> bool:
        """Check if metric name matches any pattern."""
        return any(pattern in metric_name for pattern in patterns)

    def _calculate_correlation_score(
        self,
        anomaly1: AnomalyDetection,
        anomaly2: AnomalyDetection,
    ) -> float:
        """Calculate correlation score between two anomalies."""
        # Base score from confidence
        score = (anomaly1.confidence_score + anomaly2.confidence_score) / 2

        # Boost for same labels (same namespace, pod, etc.)
        shared_labels = set(anomaly1.labels.keys()) & set(anomaly2.labels.keys())
        label_match = sum(1 for k in shared_labels if anomaly1.labels[k] == anomaly2.labels[k])
        score += label_match * 0.1

        # Boost for close timing
        time_diff = abs((anomaly1.detected_at - anomaly2.detected_at).total_seconds())
        if time_diff < 60:
            score += 0.2
        elif time_diff < 300:
            score += 0.1

        return min(score, 1.0)

    def _identify_root_causes(
        self,
        anomalies: list[AnomalyDetection],
        temporal_correlations: dict,
        metric_correlations: dict,
    ) -> list[RootCause]:
        """Identify root causes from correlations."""
        root_causes = []
        processed: set[str] = set()

        # Sort by number of correlated anomalies (more effects = more likely root cause)
        sorted_by_effects = sorted(
            anomalies,
            key=lambda a: len(temporal_correlations.get(str(a.id), [])),
            reverse=True,
        )

        for anomaly in sorted_by_effects:
            anomaly_id = str(anomaly.id)
            if anomaly_id in processed:
                continue

            temporal = temporal_correlations.get(anomaly_id, [])
            metric = metric_correlations.get(anomaly_id, [])

            if not temporal and not metric:
                continue

            # Build correlated anomalies list
            correlated = []

            for other, time_lag in temporal:
                correlated.append(
                    CorrelatedAnomaly(
                        anomaly=other,
                        correlation_score=0.8,
                        time_lag_seconds=time_lag,
                        relationship="symptom_of",
                    )
                )
                processed.add(str(other.id))

            for other_id, score in metric:
                other = next((a for a in anomalies if str(a.id) == other_id), None)
                if other and other_id not in processed:
                    correlated.append(
                        CorrelatedAnomaly(
                            anomaly=other,
                            correlation_score=score,
                            time_lag_seconds=0,
                            relationship="correlated_with",
                        )
                    )
                    processed.add(other_id)

            if correlated:
                # Generate root cause
                root_cause = RootCause(
                    id=f"rca-{uuid4().hex[:8]}",
                    cluster_id=str(anomaly.cluster_id),
                    identified_at=datetime.now(UTC),
                    confidence=self._calculate_rca_confidence(anomaly, correlated),
                    primary_anomaly=anomaly,
                    correlated_anomalies=correlated,
                    probable_cause=self._generate_probable_cause(anomaly, correlated),
                    recommended_actions=self._generate_recommendations(anomaly, correlated),
                    evidence={
                        "temporal_correlations": len(temporal),
                        "metric_correlations": len(metric),
                        "severity": anomaly.severity.value,
                    },
                )
                root_causes.append(root_cause)
                processed.add(anomaly_id)

        return root_causes

    def _calculate_rca_confidence(
        self,
        primary: AnomalyDetection,
        correlated: list[CorrelatedAnomaly],
    ) -> float:
        """Calculate confidence in root cause identification."""
        base_confidence = primary.confidence_score

        # More correlated anomalies = higher confidence
        correlation_boost = min(len(correlated) * 0.1, 0.3)

        # Higher correlation scores = higher confidence
        avg_correlation = (
            sum(c.correlation_score for c in correlated) / len(correlated) if correlated else 0
        )

        return min(base_confidence + correlation_boost + avg_correlation * 0.2, 1.0)

    def _generate_probable_cause(
        self,
        primary: AnomalyDetection,
        correlated: list[CorrelatedAnomaly],
    ) -> str:
        """Generate probable cause description."""
        component = self._get_component(primary.metric_name)

        count = len(correlated)
        cause_templates = {
            "node": f"Node resource exhaustion affecting {count} components",
            "container": f"Container issue propagating to {count} metrics",
            "pod": f"Pod instability causing {count} cascading failures",
            "service": f"Service degradation impacting {count} downstream metrics",
            "gpu": f"GPU resource constraint affecting {count} workloads",
        }

        return cause_templates.get(
            component,
            f"System anomaly in {primary.metric_name} with {len(correlated)} correlated issues",
        )

    def _get_component(self, metric_name: str) -> str:
        """Get component type from metric name."""
        for pattern, component in self._metric_components.items():
            if pattern in metric_name:
                return component
        return "system"

    def _generate_recommendations(
        self,
        primary: AnomalyDetection,
        correlated: list[CorrelatedAnomaly],
    ) -> list[str]:
        """Generate recommended actions."""
        recommendations = []
        metric = primary.metric_name

        if "cpu" in metric:
            recommendations.extend(
                [
                    "Check for CPU-intensive processes",
                    "Consider horizontal scaling",
                    "Review resource limits and requests",
                ]
            )
        elif "memory" in metric:
            recommendations.extend(
                [
                    "Check for memory leaks",
                    "Increase memory limits if appropriate",
                    "Review application memory usage patterns",
                ]
            )
        elif "gpu" in metric:
            recommendations.extend(
                [
                    "Review GPU workload scheduling",
                    "Check for GPU memory fragmentation",
                    "Consider workload balancing across GPUs",
                ]
            )
        elif "latency" in metric or "5xx" in metric:
            recommendations.extend(
                [
                    "Check backend service health",
                    "Review recent deployments",
                    "Examine database query performance",
                ]
            )

        # Add generic recommendations
        recommendations.append(f"Investigate primary anomaly in {metric}")
        recommendations.append("Review logs from affected components")

        return recommendations


# Singleton instance
rca_analyzer = RootCauseAnalyzer()
