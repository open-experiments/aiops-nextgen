"""Unit tests for Pydantic models.

Spec Reference: specs/01-data-models.md
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from shared.models import (
    Alert,
    AlertSeverity,
    AlertState,
    AnomalyDetection,
    AnomalySeverity,
    AnomalyType,
    ChatMessage,
    ChatSession,
    Cluster,
    ClusterCapabilities,
    ClusterCreate,
    ClusterEndpoints,
    ClusterState,
    ClusterStatus,
    ClusterType,
    ClusterUpdate,
    DetectionType,
    Environment,
    Event,
    EventType,
    GPU,
    GPUNode,
    GPUProcess,
    GPUProcessType,
    LogEntry,
    LogQuery,
    MessageRole,
    MetricQuery,
    MetricResult,
    MetricResultStatus,
    MetricResultType,
    MetricSeries,
    Persona,
    Platform,
    Report,
    ReportFormat,
    ReportRequest,
    ReportType,
    Span,
    SpanStatus,
    Subscription,
    SubscriptionRequest,
    TimeRange,
    ToolCall,
    ToolResult,
    ToolResultStatus,
    Trace,
    TraceQuery,
)


class TestClusterModels:
    """Test cluster domain models."""

    def test_cluster_create_minimal(self) -> None:
        """Test creating cluster with minimal required fields."""
        cluster = ClusterCreate(
            name="test-cluster",
            api_server_url="https://api.test.example.com:6443",
        )
        assert cluster.name == "test-cluster"
        assert cluster.cluster_type == ClusterType.SPOKE  # default
        assert cluster.platform == Platform.OPENSHIFT  # default
        assert cluster.environment == Environment.DEVELOPMENT  # default

    def test_cluster_create_full(self) -> None:
        """Test creating cluster with all fields."""
        cluster = ClusterCreate(
            name="prod-east-01",
            display_name="Production East 01",
            api_server_url="https://api.prod-east.example.com:6443",
            cluster_type=ClusterType.SPOKE,
            platform=Platform.OPENSHIFT,
            platform_version="4.16.0",
            region="us-east-1",
            environment=Environment.PRODUCTION,
            labels={"team": "platform"},
            endpoints=ClusterEndpoints(
                prometheus="https://prometheus.prod-east.example.com",
                tempo="https://tempo.prod-east.example.com",
                loki="https://loki.prod-east.example.com",
            ),
            capabilities=ClusterCapabilities(
                gpu=True,
                gpu_types=["NVIDIA A100"],
            ),
        )
        assert cluster.cluster_type == ClusterType.SPOKE
        assert cluster.environment == Environment.PRODUCTION
        assert cluster.capabilities is not None
        assert cluster.capabilities.gpu is True

    def test_cluster_status(self) -> None:
        """Test ClusterStatus model."""
        status = ClusterStatus(
            state=ClusterState.ONLINE,
            message="All systems operational",
        )
        assert status.state == ClusterState.ONLINE
        assert status.connectivity is None  # optional

    def test_cluster_update_partial(self) -> None:
        """Test partial cluster update."""
        update = ClusterUpdate(display_name="New Display Name")
        assert update.display_name == "New Display Name"
        assert update.labels is None  # not updated

    def test_cluster_full_model(self, sample_cluster_data: dict) -> None:
        """Test full Cluster model."""
        cluster = Cluster(
            id=uuid4(),
            name=sample_cluster_data["name"],
            api_server_url=sample_cluster_data["api_server_url"],
            cluster_type=ClusterType.SPOKE,
            platform=Platform.OPENSHIFT,
            environment=Environment.DEVELOPMENT,
            status=ClusterStatus(state=ClusterState.ONLINE),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert cluster.name == sample_cluster_data["name"]


class TestObservabilityModels:
    """Test observability domain models."""

    def test_metric_query(self) -> None:
        """Test MetricQuery model."""
        query = MetricQuery(
            query="up{job='prometheus'}",
            start=datetime.now(timezone.utc),
            end=datetime.now(timezone.utc),
        )
        assert "up" in query.query

    def test_metric_result(self) -> None:
        """Test MetricResult model."""
        result = MetricResult(
            status=MetricResultStatus.SUCCESS,
            result_type=MetricResultType.VECTOR,
            result=[
                MetricSeries(
                    metric={"__name__": "up", "job": "prometheus"},
                    values=[[1703424000, "1"]],
                )
            ],
        )
        assert result.status == MetricResultStatus.SUCCESS
        assert len(result.result) == 1

    def test_alert_model(self) -> None:
        """Test Alert model."""
        alert = Alert(
            alert_id=str(uuid4()),
            name="HighMemoryUsage",
            severity=AlertSeverity.WARNING,
            state=AlertState.FIRING,
            labels={"pod": "nginx-abc123"},
            annotations={"description": "Memory usage above 80%"},
            started_at=datetime.now(timezone.utc),
            cluster_id=uuid4(),
        )
        assert alert.severity == AlertSeverity.WARNING
        assert alert.state == AlertState.FIRING

    def test_trace_model(self) -> None:
        """Test Trace and Span models."""
        span = Span(
            trace_id="abc123",
            span_id="def456",
            operation_name="HTTP GET",
            service_name="api-gateway",
            duration_ms=150.5,
            status=SpanStatus.OK,
            start_time=datetime.now(timezone.utc),
        )
        trace = Trace(
            trace_id="abc123",
            root_service="api-gateway",
            root_operation="HTTP GET",
            duration_ms=150.5,
            span_count=1,
            has_errors=False,
            start_time=datetime.now(timezone.utc),
            spans=[span],
        )
        assert trace.span_count == 1
        assert not trace.has_errors

    def test_log_entry(self) -> None:
        """Test LogEntry model."""
        log = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level="ERROR",
            message="Connection refused",
            labels={"app": "nginx", "namespace": "default"},
            cluster_id=uuid4(),
        )
        assert log.level == "ERROR"


class TestGPUModels:
    """Test GPU domain models."""

    def test_gpu_model(self) -> None:
        """Test GPU model."""
        gpu = GPU(
            index=0,
            name="NVIDIA A100-SXM4-40GB",
            uuid="GPU-12345678",
            memory_total_mib=40960,
            memory_used_mib=8192,
            memory_free_mib=32768,
            temperature_c=45,
            utilization_percent=25.5,
            power_draw_w=150.0,
            power_limit_w=400.0,
        )
        assert gpu.memory_total_mib == 40960
        assert gpu.utilization_percent == 25.5

    def test_gpu_node(self) -> None:
        """Test GPUNode model."""
        gpu = GPU(
            index=0,
            name="NVIDIA A100",
            uuid="GPU-123",
            memory_total_mib=40960,
            memory_used_mib=8192,
            memory_free_mib=32768,
            utilization_percent=50.0,
        )
        node = GPUNode(
            node_name="gpu-node-1",
            cluster_id=uuid4(),
            gpu_count=2,
            gpus=[gpu],
            total_memory_mib=81920,
            used_memory_mib=16384,
            average_utilization=50.0,
            collected_at=datetime.now(timezone.utc),
        )
        assert node.gpu_count == 2
        assert len(node.gpus) == 1


class TestIntelligenceModels:
    """Test intelligence domain models."""

    def test_persona_model(self) -> None:
        """Test Persona model."""
        persona = Persona(
            id="kubernetes-expert",
            name="Kubernetes Expert",
            description="Expert in Kubernetes troubleshooting",
            system_prompt="You are a Kubernetes expert...",
            available_tools=["get_pods", "get_events", "query_metrics"],
        )
        assert len(persona.available_tools) == 3

    def test_chat_session(self, sample_chat_session_data: dict) -> None:
        """Test ChatSession model."""
        session = ChatSession(
            id=uuid4(),
            user_id=sample_chat_session_data["user_id"],
            persona_id=sample_chat_session_data["persona_id"],
            message_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert session.persona_id == "kubernetes-expert"

    def test_chat_message(self) -> None:
        """Test ChatMessage model."""
        message = ChatMessage(
            id=uuid4(),
            session_id=uuid4(),
            role=MessageRole.USER,
            content="What pods are failing?",
            created_at=datetime.now(timezone.utc),
        )
        assert message.role == MessageRole.USER

    def test_tool_call_and_result(self) -> None:
        """Test ToolCall and ToolResult models."""
        tool_call = ToolCall(
            id="call_123",
            name="get_pods",
            arguments={"namespace": "default", "status": "Failed"},
        )
        tool_result = ToolResult(
            tool_call_id="call_123",
            status=ToolResultStatus.SUCCESS,
            output={"pods": [{"name": "nginx-abc", "status": "CrashLoopBackOff"}]},
        )
        assert tool_call.name == "get_pods"
        assert tool_result.status == ToolResultStatus.SUCCESS

    def test_anomaly_detection(self) -> None:
        """Test AnomalyDetection model."""
        anomaly = AnomalyDetection(
            id=uuid4(),
            cluster_id=uuid4(),
            metric_name="container_cpu_usage_seconds_total",
            detection_type=DetectionType.STATISTICAL,
            severity=AnomalySeverity.HIGH,
            confidence_score=0.95,
            anomaly_type=AnomalyType.SPIKE,
            expected_value=0.5,
            actual_value=0.95,
            deviation_percent=90.0,
            explanation="CPU usage spiked 90% above normal",
            detected_at=datetime.now(timezone.utc),
        )
        assert anomaly.severity == AnomalySeverity.HIGH
        assert anomaly.confidence_score == 0.95


class TestEventModels:
    """Test event domain models."""

    def test_event_model(self, sample_event_data: dict) -> None:
        """Test Event model."""
        event = Event(
            event_id=uuid4(),
            event_type=EventType.CLUSTER_REGISTERED,
            source="cluster-registry",
            cluster_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            payload={"name": "new-cluster"},
        )
        assert event.event_type == EventType.CLUSTER_REGISTERED

    def test_subscription_model(self) -> None:
        """Test Subscription model."""
        subscription = Subscription(
            id=uuid4(),
            client_id="client-123",
            event_types=[EventType.ALERT_FIRED, EventType.ALERT_RESOLVED],
            cluster_filter=[uuid4()],
            created_at=datetime.now(timezone.utc),
        )
        assert len(subscription.event_types) == 2


class TestReportModels:
    """Test report domain models."""

    def test_report_request(self) -> None:
        """Test ReportRequest model."""
        request = ReportRequest(
            title="Weekly Status Report",
            report_type=ReportType.EXECUTIVE_SUMMARY,
            format=ReportFormat.PDF,
        )
        assert request.format == ReportFormat.PDF

    def test_report_model(self) -> None:
        """Test Report model."""
        report = Report(
            id=uuid4(),
            title="Weekly Status Report",
            report_type=ReportType.EXECUTIVE_SUMMARY,
            format=ReportFormat.PDF,
            generated_by="user@example.com",
            storage_path="/reports/weekly-2024-12-24.pdf",
            size_bytes=1024000,
            created_at=datetime.now(timezone.utc),
        )
        assert report.report_type == ReportType.EXECUTIVE_SUMMARY


class TestCommonModels:
    """Test common utility models."""

    def test_time_range(self) -> None:
        """Test TimeRange model."""
        time_range = TimeRange(
            start=datetime(2024, 12, 24, 0, 0, tzinfo=timezone.utc),
            end=datetime(2024, 12, 24, 23, 59, tzinfo=timezone.utc),
        )
        assert time_range.start < time_range.end
