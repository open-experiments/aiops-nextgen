"""GPU domain models.

Spec Reference: specs/01-data-models.md Section 4 - GPU Domain Models
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from .base import AIOpsBaseModel


class GPUProcessType(str, Enum):
    """Type of GPU process. Spec: Section 4.3"""

    COMPUTE = "COMPUTE"
    GRAPHICS = "GRAPHICS"
    MIXED = "MIXED"


class GPUProcess(AIOpsBaseModel):
    """A process running on a GPU.

    Spec Reference: Section 4.3
    """

    pid: int
    process_name: str
    used_memory_mb: int
    type: GPUProcessType


class GPU(AIOpsBaseModel):
    """A single GPU device.

    Spec Reference: Section 4.2
    """

    index: int = Field(description="GPU index on the node")
    uuid: str = Field(description="NVIDIA GPU UUID")
    name: str
    driver_version: str
    cuda_version: str | None = None
    memory_total_mb: int
    memory_used_mb: int
    memory_free_mb: int
    utilization_gpu_percent: int = Field(ge=0, le=100)
    utilization_memory_percent: int = Field(ge=0, le=100)
    temperature_celsius: int
    power_draw_watts: float
    power_limit_watts: float
    fan_speed_percent: int | None = Field(default=None, ge=0, le=100)
    processes: list[GPUProcess] = Field(default_factory=list)


class GPUNode(AIOpsBaseModel):
    """A node with GPU(s) in a cluster.

    Spec Reference: Section 4.1
    """

    cluster_id: UUID
    cluster_name: str
    node_name: str
    gpus: list[GPU] = Field(default_factory=list)
    last_updated: datetime
