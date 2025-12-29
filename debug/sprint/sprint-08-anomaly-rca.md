# Sprint 8: Anomaly Detection & Root Cause Analysis

**Issues Addressed:** ISSUE-007 (HIGH), ISSUE-008 (HIGH)
**Priority:** P1
**Dependencies:** Sprint 1, Sprint 3, Sprint 4

---

## Overview

This sprint implements the anomaly detection engine and root cause analysis (RCA) service. Currently these are stubbed out. The implementation uses statistical methods for anomaly detection and correlation analysis for RCA.

---

## Task 8.1: Anomaly Detection Service

**File:** `src/intelligence-engine/services/anomaly_detection.py`

### Implementation

```python
"""Anomaly Detection Service.

Spec Reference: specs/04-intelligence-engine.md Section 4

Implements multi-method anomaly detection:
- Statistical: Z-score, IQR, Isolation Forest
- Pattern-based: Seasonal decomposition
- ML-based: Local outlier factor
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from enum import Enum
import numpy as np
from collections import deque

from pydantic import BaseModel

from shared.models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    DetectionType,
    MetricSeries,
)
from shared.observability import get_logger

logger = get_logger(__name__)


class DetectionMethod(str, Enum):
    """Available detection methods."""

    ZSCORE = "zscore"
    IQR = "iqr"
    ISOLATION_FOREST = "isolation_forest"
    SEASONAL = "seasonal"
    LOF = "lof"  # Local Outlier Factor


class AnomalyConfig(BaseModel):
    """Configuration for anomaly detection."""

    zscore_threshold: float = 3.0
    iqr_multiplier: float = 1.5
    isolation_contamination: float = 0.1
    seasonal_period: int = 24  # hours
    lof_neighbors: int = 20
    min_data_points: int = 30


class DetectionResult(BaseModel):
    """Result of anomaly detection."""

    is_anomaly: bool
    score: float
    method: DetectionMethod
    threshold: float
    confidence: float
    details: dict


class AnomalyDetector:
    """Multi-method anomaly detection engine."""

    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or AnomalyConfig()
        self._history: dict[str, deque] = {}  # metric_key -> historical values

    def detect(
        self,
        metric_series: MetricSeries,
        methods: Optional[list[DetectionMethod]] = None,
    ) -> list[AnomalyDetection]:
        """Detect anomalies in a metric series.

        Args:
            metric_series: Metric time series data
            methods: Detection methods to use (defaults to all)

        Returns:
            List of detected anomalies
        """
        if not methods:
            methods = [DetectionMethod.ZSCORE, DetectionMethod.IQR]

        values = [v["value"] for v in metric_series.values]
        timestamps = [v["timestamp"] for v in metric_series.values]

        if len(values) < self.config.min_data_points:
            logger.debug(
                "Insufficient data for anomaly detection",
                metric=metric_series.metric,
                count=len(values),
            )
            return []

        anomalies = []

        for method in methods:
            results = self._detect_with_method(values, timestamps, method)

            for timestamp, result in results:
                if result.is_anomaly:
                    severity = self._calculate_severity(result.score, result.threshold)

                    anomaly = AnomalyDetection(
                        id=f"{metric_series.metric}-{timestamp}",
                        cluster_id=metric_series.labels.get("cluster_id", "unknown"),
                        metric=metric_series.metric,
                        labels=metric_series.labels,
                        detected_at=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                        severity=severity,
                        anomaly_type=self._classify_anomaly_type(result),
                        detection_type=self._map_detection_type(method),
                        score=result.score,
                        threshold=result.threshold,
                        confidence=result.confidence,
                        description=self._generate_description(
                            metric_series.metric, result
                        ),
                    )
                    anomalies.append(anomaly)

        return anomalies

    def _detect_with_method(
        self,
        values: list[float],
        timestamps: list[float],
        method: DetectionMethod,
    ) -> list[tuple[float, DetectionResult]]:
        """Run specific detection method.

        Args:
            values: Metric values
            timestamps: Corresponding timestamps
            method: Detection method to use

        Returns:
            List of (timestamp, DetectionResult) tuples
        """
        if method == DetectionMethod.ZSCORE:
            return self._detect_zscore(values, timestamps)
        elif method == DetectionMethod.IQR:
            return self._detect_iqr(values, timestamps)
        elif method == DetectionMethod.ISOLATION_FOREST:
            return self._detect_isolation_forest(values, timestamps)
        elif method == DetectionMethod.SEASONAL:
            return self._detect_seasonal(values, timestamps)
        elif method == DetectionMethod.LOF:
            return self._detect_lof(values, timestamps)
        else:
            return []

    def _detect_zscore(
        self,
        values: list[float],
        timestamps: list[float],
    ) -> list[tuple[float, DetectionResult]]:
        """Z-score based anomaly detection."""
        arr = np.array(values)
        mean = np.mean(arr)
        std = np.std(arr)

        if std == 0:
            return []

        results = []
        threshold = self.config.zscore_threshold

        for i, (value, ts) in enumerate(zip(values, timestamps)):
            zscore = abs((value - mean) / std)
            is_anomaly = zscore > threshold

            results.append((
                ts,
                DetectionResult(
                    is_anomaly=is_anomaly,
                    score=zscore,
                    method=DetectionMethod.ZSCORE,
                    threshold=threshold,
                    confidence=min(zscore / threshold, 1.0) if is_anomaly else 0,
                    details={"mean": mean, "std": std, "value": value},
                ),
            ))

        return results

    def _detect_iqr(
        self,
        values: list[float],
        timestamps: list[float],
    ) -> list[tuple[float, DetectionResult]]:
        """IQR (Interquartile Range) based detection."""
        arr = np.array(values)
        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1

        lower_bound = q1 - self.config.iqr_multiplier * iqr
        upper_bound = q3 + self.config.iqr_multiplier * iqr

        results = []

        for value, ts in zip(values, timestamps):
            distance = 0
            if value < lower_bound:
                distance = lower_bound - value
            elif value > upper_bound:
                distance = value - upper_bound

            is_anomaly = distance > 0
            score = distance / iqr if iqr > 0 else 0

            results.append((
                ts,
                DetectionResult(
                    is_anomaly=is_anomaly,
                    score=score,
                    method=DetectionMethod.IQR,
                    threshold=self.config.iqr_multiplier,
                    confidence=min(score, 1.0) if is_anomaly else 0,
                    details={
                        "q1": q1,
                        "q3": q3,
                        "iqr": iqr,
                        "lower_bound": lower_bound,
                        "upper_bound": upper_bound,
                    },
                ),
            ))

        return results

    def _detect_isolation_forest(
        self,
        values: list[float],
        timestamps: list[float],
    ) -> list[tuple[float, DetectionResult]]:
        """Isolation Forest based detection."""
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.warning("sklearn not available for Isolation Forest")
            return []

        arr = np.array(values).reshape(-1, 1)

        model = IsolationForest(
            contamination=self.config.isolation_contamination,
            random_state=42,
        )
        predictions = model.fit_predict(arr)
        scores = model.score_samples(arr)

        results = []

        for i, (pred, score, ts) in enumerate(zip(predictions, scores, timestamps)):
            is_anomaly = pred == -1

            results.append((
                ts,
                DetectionResult(
                    is_anomaly=is_anomaly,
                    score=abs(score),
                    method=DetectionMethod.ISOLATION_FOREST,
                    threshold=self.config.isolation_contamination,
                    confidence=abs(score) if is_anomaly else 0,
                    details={"prediction": int(pred)},
                ),
            ))

        return results

    def _detect_seasonal(
        self,
        values: list[float],
        timestamps: list[float],
    ) -> list[tuple[float, DetectionResult]]:
        """Seasonal decomposition based detection."""
        try:
            from statsmodels.tsa.seasonal import seasonal_decompose
        except ImportError:
            logger.warning("statsmodels not available for seasonal detection")
            return []

        if len(values) < 2 * self.config.seasonal_period:
            return []

        arr = np.array(values)

        try:
            decomposition = seasonal_decompose(
                arr,
                period=self.config.seasonal_period,
                extrapolate_trend="freq",
            )
            residual = decomposition.resid

            # Detect anomalies in residual using z-score
            residual_clean = residual[~np.isnan(residual)]
            mean_res = np.mean(residual_clean)
            std_res = np.std(residual_clean)

            results = []
            threshold = self.config.zscore_threshold

            for i, (res, ts) in enumerate(zip(residual, timestamps)):
                if np.isnan(res):
                    continue

                zscore = abs((res - mean_res) / std_res) if std_res > 0 else 0
                is_anomaly = zscore > threshold

                results.append((
                    ts,
                    DetectionResult(
                        is_anomaly=is_anomaly,
                        score=zscore,
                        method=DetectionMethod.SEASONAL,
                        threshold=threshold,
                        confidence=min(zscore / threshold, 1.0) if is_anomaly else 0,
                        details={
                            "trend": float(decomposition.trend[i]),
                            "seasonal": float(decomposition.seasonal[i]),
                            "residual": float(res),
                        },
                    ),
                ))

            return results

        except Exception as e:
            logger.warning("Seasonal decomposition failed", error=str(e))
            return []

    def _detect_lof(
        self,
        values: list[float],
        timestamps: list[float],
    ) -> list[tuple[float, DetectionResult]]:
        """Local Outlier Factor based detection."""
        try:
            from sklearn.neighbors import LocalOutlierFactor
        except ImportError:
            logger.warning("sklearn not available for LOF")
            return []

        arr = np.array(values).reshape(-1, 1)

        model = LocalOutlierFactor(
            n_neighbors=min(self.config.lof_neighbors, len(values) - 1),
            contamination=self.config.isolation_contamination,
        )
        predictions = model.fit_predict(arr)
        scores = -model.negative_outlier_factor_

        results = []

        for pred, score, ts in zip(predictions, scores, timestamps):
            is_anomaly = pred == -1

            results.append((
                ts,
                DetectionResult(
                    is_anomaly=is_anomaly,
                    score=score,
                    method=DetectionMethod.LOF,
                    threshold=1.5,  # LOF threshold
                    confidence=min(score - 1, 1.0) if is_anomaly else 0,
                    details={"lof_score": score},
                ),
            ))

        return results

    def _calculate_severity(self, score: float, threshold: float) -> AnomalySeverity:
        """Calculate anomaly severity from score."""
        ratio = score / threshold if threshold > 0 else score

        if ratio > 5:
            return AnomalySeverity.CRITICAL
        elif ratio > 3:
            return AnomalySeverity.HIGH
        elif ratio > 2:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW

    def _classify_anomaly_type(self, result: DetectionResult) -> AnomalyType:
        """Classify the type of anomaly."""
        score = result.score

        if score > result.threshold * 3:
            return AnomalyType.SPIKE
        elif result.details.get("trend"):
            return AnomalyType.TREND_CHANGE
        else:
            return AnomalyType.POINT

    def _map_detection_type(self, method: DetectionMethod) -> DetectionType:
        """Map detection method to detection type."""
        if method in [DetectionMethod.ZSCORE, DetectionMethod.IQR]:
            return DetectionType.STATISTICAL
        elif method == DetectionMethod.SEASONAL:
            return DetectionType.PATTERN
        else:
            return DetectionType.ML

    def _generate_description(
        self,
        metric: str,
        result: DetectionResult,
    ) -> str:
        """Generate human-readable anomaly description."""
        method_names = {
            DetectionMethod.ZSCORE: "Z-score analysis",
            DetectionMethod.IQR: "IQR analysis",
            DetectionMethod.ISOLATION_FOREST: "Isolation Forest",
            DetectionMethod.SEASONAL: "Seasonal decomposition",
            DetectionMethod.LOF: "Local Outlier Factor",
        }

        return (
            f"Anomaly detected in {metric} using {method_names[result.method]}. "
            f"Score: {result.score:.2f} (threshold: {result.threshold:.2f}). "
            f"Confidence: {result.confidence * 100:.0f}%."
        )


# Singleton instance
anomaly_detector = AnomalyDetector()
```

---

## Task 8.2: Root Cause Analysis Service

**File:** `src/intelligence-engine/services/rca.py`

### Implementation

```python
"""Root Cause Analysis Service.

Spec Reference: specs/04-intelligence-engine.md Section 5

Implements correlation-based root cause analysis:
- Temporal correlation of anomalies
- Metric correlation analysis
- Dependency graph traversal
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
import numpy as np

from pydantic import BaseModel

from shared.models import AnomalyDetection, AnomalySeverity
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


class DependencyNode(BaseModel):
    """Node in the dependency graph."""

    name: str
    node_type: str  # "service", "pod", "node", "component"
    metrics: list[str]
    depends_on: list[str]


class RCAConfig(BaseModel):
    """Configuration for root cause analysis."""

    time_window_minutes: int = 30
    correlation_threshold: float = 0.7
    max_time_lag_seconds: float = 300
    min_anomalies_for_rca: int = 2


class RootCauseAnalyzer:
    """Root cause analysis engine."""

    def __init__(self, config: Optional[RCAConfig] = None):
        self.config = config or RCAConfig()

        # Known dependency patterns
        self._dependencies: dict[str, list[str]] = {
            "container_cpu_usage": ["node_cpu_usage"],
            "container_memory_usage": ["node_memory_usage"],
            "pod_restarts": ["container_oom_kills", "node_memory_pressure"],
            "http_request_latency": ["database_query_time", "network_latency"],
            "http_5xx_errors": ["pod_restarts", "container_cpu_throttling"],
            "gpu_memory_usage": ["gpu_utilization"],
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
            by_cluster[anomaly.cluster_id].append(anomaly)

        root_causes = []

        for cluster_id, cluster_anomalies in by_cluster.items():
            # Sort by time
            sorted_anomalies = sorted(
                cluster_anomalies, key=lambda a: a.detected_at
            )

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
        correlations = defaultdict(list)
        max_lag = self.config.max_time_lag_seconds

        for i, anomaly in enumerate(anomalies):
            for j, other in enumerate(anomalies):
                if i == j:
                    continue

                time_diff = (other.detected_at - anomaly.detected_at).total_seconds()

                # Look for anomalies that occurred after this one (effects)
                if 0 < time_diff <= max_lag:
                    correlations[anomaly.id].append((other, time_diff))

        return correlations

    def _find_metric_correlations(
        self,
        anomalies: list[AnomalyDetection],
    ) -> dict[str, list[tuple[str, float]]]:
        """Find correlations based on known metric dependencies.

        Returns dict mapping anomaly ID to list of (correlated_anomaly_id, score).
        """
        correlations = defaultdict(list)

        anomaly_metrics = {a.id: a.metric for a in anomalies}

        for anomaly in anomalies:
            # Check if this metric is a known effect of other metrics
            for dep_metric, effects in self._dependencies.items():
                if anomaly.metric in effects:
                    # Look for anomalies in the dependency metric
                    for other in anomalies:
                        if other.metric == dep_metric and other.id != anomaly.id:
                            # Calculate correlation score based on severity
                            score = self._calculate_correlation_score(anomaly, other)
                            if score >= self.config.correlation_threshold:
                                correlations[anomaly.id].append((other.id, score))

        return correlations

    def _calculate_correlation_score(
        self,
        anomaly1: AnomalyDetection,
        anomaly2: AnomalyDetection,
    ) -> float:
        """Calculate correlation score between two anomalies."""
        # Base score from confidence
        score = (anomaly1.confidence + anomaly2.confidence) / 2

        # Boost for same labels (same namespace, pod, etc.)
        shared_labels = set(anomaly1.labels.keys()) & set(anomaly2.labels.keys())
        label_match = sum(
            1 for k in shared_labels
            if anomaly1.labels[k] == anomaly2.labels[k]
        )
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
        processed = set()

        # Sort by number of correlated anomalies (more effects = more likely root cause)
        sorted_by_effects = sorted(
            anomalies,
            key=lambda a: len(temporal_correlations.get(a.id, [])),
            reverse=True,
        )

        for anomaly in sorted_by_effects:
            if anomaly.id in processed:
                continue

            temporal = temporal_correlations.get(anomaly.id, [])
            metric = metric_correlations.get(anomaly.id, [])

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
                processed.add(other.id)

            for other_id, score in metric:
                other = next((a for a in anomalies if a.id == other_id), None)
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
                    id=f"rca-{anomaly.id}",
                    cluster_id=anomaly.cluster_id,
                    identified_at=datetime.now(timezone.utc),
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
                processed.add(anomaly.id)

        return root_causes

    def _calculate_rca_confidence(
        self,
        primary: AnomalyDetection,
        correlated: list[CorrelatedAnomaly],
    ) -> float:
        """Calculate confidence in root cause identification."""
        base_confidence = primary.confidence

        # More correlated anomalies = higher confidence
        correlation_boost = min(len(correlated) * 0.1, 0.3)

        # Higher correlation scores = higher confidence
        avg_correlation = (
            sum(c.correlation_score for c in correlated) / len(correlated)
            if correlated
            else 0
        )

        return min(base_confidence + correlation_boost + avg_correlation * 0.2, 1.0)

    def _generate_probable_cause(
        self,
        primary: AnomalyDetection,
        correlated: list[CorrelatedAnomaly],
    ) -> str:
        """Generate probable cause description."""
        component = self._metric_components.get(primary.metric, "system")

        cause_templates = {
            "node": f"Node-level resource exhaustion affecting {len(correlated)} dependent components",
            "container": f"Container resource issue propagating to {len(correlated)} related metrics",
            "pod": f"Pod instability causing {len(correlated)} cascading failures",
            "service": f"Service degradation impacting {len(correlated)} downstream metrics",
            "gpu": f"GPU resource constraint affecting {len(correlated)} workloads",
        }

        return cause_templates.get(
            component,
            f"System anomaly in {primary.metric} with {len(correlated)} correlated issues",
        )

    def _generate_recommendations(
        self,
        primary: AnomalyDetection,
        correlated: list[CorrelatedAnomaly],
    ) -> list[str]:
        """Generate recommended actions."""
        recommendations = []
        metric = primary.metric

        if "cpu" in metric:
            recommendations.extend([
                "Check for CPU-intensive processes",
                "Consider horizontal scaling",
                "Review resource limits and requests",
            ])
        elif "memory" in metric:
            recommendations.extend([
                "Check for memory leaks",
                "Increase memory limits if appropriate",
                "Review application memory usage patterns",
            ])
        elif "gpu" in metric:
            recommendations.extend([
                "Review GPU workload scheduling",
                "Check for GPU memory fragmentation",
                "Consider workload balancing across GPUs",
            ])
        elif "latency" in metric or "5xx" in metric:
            recommendations.extend([
                "Check backend service health",
                "Review recent deployments",
                "Examine database query performance",
            ])

        # Add generic recommendations
        recommendations.append(f"Investigate primary anomaly in {metric}")
        recommendations.append(f"Review logs from affected components")

        return recommendations


# Singleton instance
rca_analyzer = RootCauseAnalyzer()
```

---

## Task 8.3: API Endpoints

**File:** `src/intelligence-engine/api/v1/anomaly.py`

```python
"""Anomaly Detection API endpoints.

Spec Reference: specs/04-intelligence-engine.md Section 7.3
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query

from services.anomaly_detection import anomaly_detector, DetectionMethod
from services.rca import rca_analyzer, RootCause
from services.metrics_client import get_cluster_metrics
from shared.models import AnomalyDetection, MetricQuery

router = APIRouter(prefix="/anomaly", tags=["anomaly"])


@router.post("/detect")
async def detect_anomalies(
    cluster_id: str,
    metric: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    methods: Optional[list[str]] = None,
) -> list[AnomalyDetection]:
    """Detect anomalies in a metric.

    Args:
        cluster_id: Target cluster ID
        metric: Metric name (PromQL query)
        start: Start time (defaults to 1 hour ago)
        end: End time (defaults to now)
        methods: Detection methods to use

    Returns:
        List of detected anomalies
    """
    if not start:
        start = datetime.now(timezone.utc) - timedelta(hours=1)
    if not end:
        end = datetime.now(timezone.utc)

    # Get metric data
    query = MetricQuery(query=metric, start=start, end=end, step="1m")
    metric_result = await get_cluster_metrics(cluster_id, query)

    if not metric_result.result:
        return []

    # Parse methods
    detection_methods = None
    if methods:
        detection_methods = [DetectionMethod(m) for m in methods]

    # Detect anomalies
    all_anomalies = []
    for series in metric_result.result:
        anomalies = anomaly_detector.detect(series, detection_methods)
        all_anomalies.extend(anomalies)

    return all_anomalies


@router.post("/rca")
async def analyze_root_cause(
    cluster_id: str,
    time_window_minutes: int = 30,
) -> list[RootCause]:
    """Perform root cause analysis on recent anomalies.

    Args:
        cluster_id: Target cluster ID
        time_window_minutes: Time window to analyze

    Returns:
        List of identified root causes
    """
    # Get recent anomalies
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=time_window_minutes)

    # Common metrics to check for anomalies
    metrics = [
        "node_cpu_seconds_total",
        "node_memory_MemAvailable_bytes",
        "container_cpu_usage_seconds_total",
        "container_memory_usage_bytes",
        "kube_pod_container_status_restarts_total",
    ]

    all_anomalies = []

    for metric in metrics:
        anomalies = await detect_anomalies(
            cluster_id=cluster_id,
            metric=metric,
            start=start,
            end=end,
        )
        all_anomalies.extend(anomalies)

    if not all_anomalies:
        return []

    # Analyze root causes
    return await rca_analyzer.analyze(all_anomalies)


@router.get("/history")
async def get_anomaly_history(
    cluster_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    severity: Optional[str] = None,
) -> list[AnomalyDetection]:
    """Get historical anomalies.

    Args:
        cluster_id: Target cluster ID
        hours: Hours of history (max 168 = 1 week)
        severity: Optional severity filter

    Returns:
        List of historical anomalies
    """
    # This would query from a database in production
    # For now, run detection on historical data
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    anomalies = await detect_anomalies(
        cluster_id=cluster_id,
        metric="container_cpu_usage_seconds_total",
        start=start,
        end=end,
    )

    if severity:
        anomalies = [a for a in anomalies if a.severity.value == severity]

    return anomalies
```

---

## Acceptance Criteria

- [x] Z-score anomaly detection works with 3.0 threshold
- [x] IQR detection identifies outliers correctly
- [x] Seasonal decomposition handles periodic patterns
- [x] ML methods (Isolation Forest, LOF) available when sklearn installed
- [x] Anomaly severity calculated from score/threshold ratio
- [x] Root cause analysis finds temporal correlations
- [x] RCA identifies metric dependencies
- [x] Recommendations generated based on metric type
- [ ] All tests pass with >80% coverage

---

## Implementation Status: COMPLETED

**Completed:** 2025-12-29

### Files Created

| File | Description |
|------|-------------|
| `src/intelligence-engine/app/services/anomaly_detection.py` | Multi-method anomaly detection engine |
| `src/intelligence-engine/app/services/rca.py` | Root cause analysis with correlations |
| `src/intelligence-engine/app/api/anomaly.py` | Anomaly detection API endpoints |

### Key Features

- 5 detection methods: Z-score, IQR, Isolation Forest, Seasonal, LOF
- Configurable thresholds and min data points
- Temporal and metric correlation analysis
- Automatic root cause recommendations

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/intelligence-engine/services/anomaly_detection.py` | CREATE | Anomaly detection service |
| `src/intelligence-engine/services/rca.py` | CREATE | Root cause analysis service |
| `src/intelligence-engine/api/v1/anomaly.py` | CREATE | Anomaly API endpoints |
| `src/intelligence-engine/tests/test_anomaly_detection.py` | CREATE | Detection tests |
| `src/intelligence-engine/tests/test_rca.py` | CREATE | RCA tests |

---

## Dependencies

### Python packages

```toml
dependencies = [
    "numpy>=1.26.0",
    "scipy>=1.11.0",  # For statistical functions
]

[project.optional-dependencies]
ml = [
    "scikit-learn>=1.3.0",  # For ML-based detection
    "statsmodels>=0.14.0",  # For seasonal decomposition
]
```
