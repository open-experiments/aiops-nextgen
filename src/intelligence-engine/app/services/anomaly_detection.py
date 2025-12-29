"""Anomaly Detection Service.

Spec Reference: specs/04-intelligence-engine.md Section 4

Implements multi-method anomaly detection:
- Statistical: Z-score, IQR, Isolation Forest
- Pattern-based: Seasonal decomposition
- ML-based: Local outlier factor
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

import numpy as np
from pydantic import BaseModel

from shared.models import (
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    DetectionType,
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
    expected_value: float
    actual_value: float
    details: dict


class MetricData(BaseModel):
    """Metric time series data for analysis."""

    metric_name: str
    cluster_id: str
    labels: dict[str, str] = {}
    values: list[dict]  # [{"timestamp": float, "value": float}, ...]


class AnomalyDetector:
    """Multi-method anomaly detection engine."""

    def __init__(self, config: AnomalyConfig | None = None):
        """Initialize the anomaly detector.

        Args:
            config: Detection configuration
        """
        self.config = config or AnomalyConfig()
        self._history: dict[str, deque] = {}

    def detect(
        self,
        metric_data: MetricData,
        methods: list[DetectionMethod] | None = None,
    ) -> list[AnomalyDetection]:
        """Detect anomalies in a metric series.

        Args:
            metric_data: Metric time series data
            methods: Detection methods to use (defaults to zscore + iqr)

        Returns:
            List of detected anomalies
        """
        if not methods:
            methods = [DetectionMethod.ZSCORE, DetectionMethod.IQR]

        values = [v["value"] for v in metric_data.values]
        timestamps = [v["timestamp"] for v in metric_data.values]

        if len(values) < self.config.min_data_points:
            logger.debug(
                "Insufficient data for anomaly detection",
                metric=metric_data.metric_name,
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
                        id=uuid4(),
                        cluster_id=uuid4(),  # Would be parsed from metric_data.cluster_id
                        metric_name=metric_data.metric_name,
                        labels=metric_data.labels,
                        detected_at=datetime.fromtimestamp(timestamp, tz=UTC),
                        severity=severity,
                        anomaly_type=self._classify_anomaly_type(result),
                        detection_type=self._map_detection_type(method),
                        confidence_score=result.confidence,
                        expected_value=result.expected_value,
                        actual_value=result.actual_value,
                        deviation_percent=self._calc_deviation(
                            result.expected_value, result.actual_value
                        ),
                        explanation=self._generate_description(
                            metric_data.metric_name, result
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
        return []

    def _detect_zscore(
        self,
        values: list[float],
        timestamps: list[float],
    ) -> list[tuple[float, DetectionResult]]:
        """Z-score based anomaly detection."""
        arr = np.array(values)
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        if std == 0:
            return []

        results = []
        threshold = self.config.zscore_threshold

        for value, ts in zip(values, timestamps, strict=True):
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
                    expected_value=mean,
                    actual_value=value,
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
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1

        lower_bound = q1 - self.config.iqr_multiplier * iqr
        upper_bound = q3 + self.config.iqr_multiplier * iqr
        median = float(np.median(arr))

        results = []

        for value, ts in zip(values, timestamps, strict=True):
            distance = 0.0
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
                    expected_value=median,
                    actual_value=value,
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
        mean = float(np.mean(arr))

        model = IsolationForest(
            contamination=self.config.isolation_contamination,
            random_state=42,
        )
        predictions = model.fit_predict(arr)
        scores = model.score_samples(arr)

        results = []

        for pred, sc, ts, value in zip(predictions, scores, timestamps, values, strict=True):
            is_anomaly = pred == -1

            results.append((
                ts,
                DetectionResult(
                    is_anomaly=is_anomaly,
                    score=abs(float(sc)),
                    method=DetectionMethod.ISOLATION_FOREST,
                    threshold=self.config.isolation_contamination,
                    confidence=abs(float(sc)) if is_anomaly else 0,
                    expected_value=mean,
                    actual_value=value,
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
            mean_res = float(np.mean(residual_clean))
            std_res = float(np.std(residual_clean))

            results = []
            threshold = self.config.zscore_threshold

            for i, (res, ts, value) in enumerate(zip(residual, timestamps, values, strict=True)):
                if np.isnan(res):
                    continue

                zscore = abs((res - mean_res) / std_res) if std_res > 0 else 0
                is_anomaly = zscore > threshold
                expected = value - float(res)

                results.append((
                    ts,
                    DetectionResult(
                        is_anomaly=is_anomaly,
                        score=zscore,
                        method=DetectionMethod.SEASONAL,
                        threshold=threshold,
                        confidence=min(zscore / threshold, 1.0) if is_anomaly else 0,
                        expected_value=expected,
                        actual_value=value,
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
        mean = float(np.mean(arr))

        model = LocalOutlierFactor(
            n_neighbors=min(self.config.lof_neighbors, len(values) - 1),
            contamination=self.config.isolation_contamination,
        )
        predictions = model.fit_predict(arr)
        scores = -model.negative_outlier_factor_

        results = []

        for pred, sc, ts, value in zip(predictions, scores, timestamps, values, strict=True):
            is_anomaly = pred == -1

            results.append((
                ts,
                DetectionResult(
                    is_anomaly=is_anomaly,
                    score=float(sc),
                    method=DetectionMethod.LOF,
                    threshold=1.5,  # LOF threshold
                    confidence=min(float(sc) - 1, 1.0) if is_anomaly else 0,
                    expected_value=mean,
                    actual_value=value,
                    details={"lof_score": float(sc)},
                ),
            ))

        return results

    def _calculate_severity(self, score: float, threshold: float) -> AnomalySeverity:
        """Calculate anomaly severity from score."""
        ratio = score / threshold if threshold > 0 else score

        if ratio > 3:
            return AnomalySeverity.HIGH
        elif ratio > 2:
            return AnomalySeverity.MEDIUM
        return AnomalySeverity.LOW

    def _classify_anomaly_type(self, result: DetectionResult) -> AnomalyType:
        """Classify the type of anomaly."""
        expected = result.expected_value
        actual = result.actual_value

        if actual > expected * 1.5:
            return AnomalyType.SPIKE
        elif actual < expected * 0.5:
            return AnomalyType.DROP
        elif result.details.get("trend"):
            return AnomalyType.TREND_CHANGE
        return AnomalyType.THRESHOLD_BREACH

    def _map_detection_type(self, method: DetectionMethod) -> DetectionType:
        """Map detection method to detection type."""
        statistical_methods = [
            DetectionMethod.ZSCORE,
            DetectionMethod.IQR,
            DetectionMethod.SEASONAL,
        ]
        if method in statistical_methods:
            return DetectionType.STATISTICAL
        return DetectionType.ML_BASED

    def _calc_deviation(self, expected: float, actual: float) -> float:
        """Calculate deviation percentage."""
        if expected == 0:
            return 100.0 if actual != 0 else 0.0
        return abs((actual - expected) / expected) * 100

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
            f"Expected: {result.expected_value:.2f}, Actual: {result.actual_value:.2f}. "
            f"Confidence: {result.confidence * 100:.0f}%."
        )


# Singleton instance
anomaly_detector = AnomalyDetector()
