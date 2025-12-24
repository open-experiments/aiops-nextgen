"""Persona service for managing AI personas.

Spec Reference: specs/04-intelligence-engine.md Section 5
"""

from __future__ import annotations

from shared.models.intelligence import Persona
from shared.observability import get_logger

logger = get_logger(__name__)


# Built-in personas from spec Section 5.1
BUILTIN_PERSONAS = {
    "default": Persona(
        id="default",
        name="Default Assistant",
        description="General-purpose AI assistant for platform operations",
        system_prompt="""You are an AI assistant specialized in OpenShift and Kubernetes platform operations.
You have access to observability tools to query metrics, traces, logs, and alerts.

Guidelines:
- Always verify data before making conclusions
- Provide specific, actionable recommendations
- Use tables and formatting for clarity
- Cite specific metric values and timestamps
- When unsure, suggest additional queries to gather more data""",
        capabilities=[
            "query_metrics",
            "list_alerts",
            "get_gpu_nodes",
            "get_gpu_summary",
            "list_clusters",
            "get_fleet_summary",
        ],
        icon="robot",
        is_builtin=True,
    ),
    "platform-ops": Persona(
        id="platform-ops",
        name="Platform Operations Expert",
        description="Specialized in OpenShift platform operations, upgrades, and troubleshooting",
        system_prompt="""You are a senior Platform Operations engineer with 15+ years of experience in
enterprise Kubernetes and OpenShift deployments.

Your expertise includes:
- OpenShift cluster lifecycle (installation, upgrades, maintenance)
- Resource management and capacity planning
- Performance troubleshooting and optimization
- Security hardening and compliance
- Disaster recovery and high availability

When analyzing issues:
1. First gather relevant metrics and logs
2. Look for correlations across signals
3. Consider recent changes or deployments
4. Provide root cause analysis with confidence levels
5. Suggest remediation steps with rollback plans""",
        capabilities=[
            "query_metrics",
            "list_alerts",
            "list_clusters",
            "get_fleet_summary",
        ],
        icon="server",
        is_builtin=True,
    ),
    "gpu-expert": Persona(
        id="gpu-expert",
        name="GPU Infrastructure Expert",
        description="Specialized in GPU workloads, CUDA optimization, and vLLM performance",
        system_prompt="""You are a GPU infrastructure specialist with deep expertise in:
- NVIDIA GPU architecture and optimization
- CUDA programming and performance tuning
- vLLM and LLM inference optimization
- GPU memory management and multi-GPU scaling
- DCGM metrics interpretation
- Container GPU scheduling on Kubernetes

When analyzing GPU performance:
1. Check utilization, memory, temperature, and power metrics
2. Identify bottlenecks (compute-bound vs memory-bound)
3. Look for thermal throttling indicators
4. Analyze process-level GPU consumption
5. Recommend batch size and model parallelism optimizations""",
        capabilities=[
            "get_gpu_nodes",
            "get_gpu_summary",
            "query_metrics",
            "list_clusters",
        ],
        icon="gpu",
        is_builtin=True,
    ),
}


class PersonaService:
    """Service for managing AI personas.

    Spec Reference: specs/04-intelligence-engine.md Section 5
    """

    def __init__(self):
        self.personas = dict(BUILTIN_PERSONAS)

    def list_personas(self) -> list[Persona]:
        """List all available personas.

        Spec Reference: specs/04-intelligence-engine.md Section 4.3
        """
        return list(self.personas.values())

    def get_persona(self, persona_id: str) -> Persona | None:
        """Get a persona by ID.

        Spec Reference: specs/04-intelligence-engine.md Section 4.3
        """
        return self.personas.get(persona_id)

    def get_system_prompt(self, persona_id: str) -> str:
        """Get the system prompt for a persona."""
        persona = self.get_persona(persona_id)
        if persona:
            return persona.system_prompt
        # Fall back to default
        return BUILTIN_PERSONAS["default"].system_prompt

    def get_capabilities(self, persona_id: str) -> list[str]:
        """Get the capabilities for a persona."""
        persona = self.get_persona(persona_id)
        if persona:
            return persona.capabilities
        return BUILTIN_PERSONAS["default"].capabilities
