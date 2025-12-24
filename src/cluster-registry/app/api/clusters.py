"""Cluster CRUD API endpoints.

Spec Reference: specs/02-cluster-registry.md Section 4.1
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from shared.observability import get_logger

from ..schemas.cluster import (
    ClusterCreateRequest,
    ClusterUpdateRequest,
    ClusterResponse,
    ClusterListResponse,
    ClusterFilters,
    ClusterStatus,
)
from ..schemas.credentials import (
    CredentialInput,
    CredentialStatus,
    ValidationResult,
)
from ..services.cluster_service import (
    ClusterService,
    ClusterNotFoundError,
    ClusterAlreadyExistsError,
)
from ..services.credential_service import CredentialService

logger = get_logger(__name__)

router = APIRouter()


def get_cluster_service(request: Request) -> ClusterService:
    """Dependency to get ClusterService with database session."""
    from ..main import settings

    # Create a new session for this request
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    # We'll use a context manager approach in the actual endpoints
    return ClusterService, session_factory, redis


def get_credential_service(request: Request) -> CredentialService:
    """Dependency to get CredentialService."""
    return CredentialService(request.app.state.redis)


# =============================================================================
# Cluster CRUD Endpoints
# Spec Reference: specs/02-cluster-registry.md Section 4.1
# =============================================================================


@router.post(
    "/clusters",
    response_model=ClusterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new cluster",
    description="Register a new cluster in the fleet. See spec section 4.2 for request format.",
)
async def create_cluster(
    request: Request,
    cluster_data: ClusterCreateRequest,
):
    """Register a new cluster.

    Spec Reference: specs/02-cluster-registry.md Section 4.1, 4.2
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            return await service.create(cluster_data)
        except ClusterAlreadyExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "CLUSTER_ALREADY_EXISTS", "message": str(e)},
            )


@router.get(
    "/clusters",
    response_model=ClusterListResponse,
    summary="List all clusters",
    description="List all clusters with optional filtering and pagination.",
)
async def list_clusters(
    request: Request,
    name: str | None = Query(None, description="Filter by cluster name (partial match)"),
    cluster_type: str | None = Query(None, description="Filter by type"),
    environment: str | None = Query(None, description="Filter by environment"),
    region: str | None = Query(None, description="Filter by region"),
    state: str | None = Query(None, description="Filter by status state"),
    has_gpu: bool | None = Query(None, description="Filter clusters with GPU"),
    has_cnf: bool | None = Query(None, description="Filter clusters with CNF"),
    label: str | None = Query(None, description="Filter by label (key=value)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """List clusters with filtering.

    Spec Reference: specs/02-cluster-registry.md Section 4.1, 4.3
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    # Build filters
    from shared.models.cluster import ClusterType, Environment, ClusterState

    filters = ClusterFilters(
        name=name,
        cluster_type=ClusterType(cluster_type) if cluster_type else None,
        environment=Environment(environment) if environment else None,
        region=region,
        state=ClusterState(state) if state else None,
        has_gpu=has_gpu,
        has_cnf=has_cnf,
        label=label,
        page=page,
        page_size=page_size,
    )

    async with session_factory() as session:
        service = ClusterService(session, redis)
        return await service.list(filters)


@router.get(
    "/clusters/{cluster_id}",
    response_model=ClusterResponse,
    summary="Get cluster by ID",
    description="Get a specific cluster by its UUID.",
)
async def get_cluster(
    request: Request,
    cluster_id: UUID,
):
    """Get cluster by ID.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            return await service.get(cluster_id)
        except ClusterNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CLUSTER_NOT_FOUND", "message": str(e)},
            )


@router.get(
    "/clusters/by-name/{name}",
    response_model=ClusterResponse,
    summary="Get cluster by name",
    description="Get a specific cluster by its unique name.",
)
async def get_cluster_by_name(
    request: Request,
    name: str,
):
    """Get cluster by name.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            return await service.get_by_name(name)
        except ClusterNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CLUSTER_NOT_FOUND", "message": str(e)},
            )


@router.put(
    "/clusters/{cluster_id}",
    response_model=ClusterResponse,
    summary="Update cluster",
    description="Update cluster metadata.",
)
async def update_cluster(
    request: Request,
    cluster_id: UUID,
    update_data: ClusterUpdateRequest,
):
    """Update cluster metadata.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            return await service.update(cluster_id, update_data)
        except ClusterNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CLUSTER_NOT_FOUND", "message": str(e)},
            )


@router.delete(
    "/clusters/{cluster_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete cluster",
    description="Delete a cluster from the registry.",
)
async def delete_cluster(
    request: Request,
    cluster_id: UUID,
):
    """Delete a cluster.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            await service.delete(cluster_id)
        except ClusterNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CLUSTER_NOT_FOUND", "message": str(e)},
            )


@router.get(
    "/clusters/{cluster_id}/status",
    response_model=ClusterStatus,
    summary="Get cluster status",
    description="Get the current status of a cluster.",
)
async def get_cluster_status(
    request: Request,
    cluster_id: UUID,
):
    """Get cluster status.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            cluster = await service.get(cluster_id)
            return cluster.status
        except ClusterNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CLUSTER_NOT_FOUND", "message": str(e)},
            )


@router.post(
    "/clusters/{cluster_id}/refresh",
    response_model=ClusterResponse,
    summary="Force refresh cluster",
    description="Force refresh cluster status and capabilities.",
)
async def refresh_cluster(
    request: Request,
    cluster_id: UUID,
):
    """Force refresh cluster data.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            return await service.refresh(cluster_id)
        except ClusterNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CLUSTER_NOT_FOUND", "message": str(e)},
            )


# =============================================================================
# Credential Management Endpoints
# Spec Reference: specs/02-cluster-registry.md Section 4.1
# =============================================================================


@router.post(
    "/clusters/{cluster_id}/credentials",
    response_model=CredentialStatus,
    summary="Upload credentials",
    description="Upload credentials for cluster access.",
)
async def upload_credentials(
    request: Request,
    cluster_id: UUID,
    credentials: CredentialInput,
):
    """Upload cluster credentials.

    Spec Reference: specs/02-cluster-registry.md Section 4.1, 4.2
    """
    # First verify cluster exists
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        service = ClusterService(session, redis)
        try:
            await service.get(cluster_id)
        except ClusterNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CLUSTER_NOT_FOUND", "message": str(e)},
            )

    cred_service = CredentialService(redis)
    return await cred_service.store(cluster_id, credentials)


@router.post(
    "/clusters/{cluster_id}/credentials/rotate",
    response_model=CredentialStatus,
    summary="Rotate credentials",
    description="Rotate cluster credentials with zero-downtime.",
)
async def rotate_credentials(
    request: Request,
    cluster_id: UUID,
    credentials: CredentialInput,
):
    """Rotate cluster credentials.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    cred_service = CredentialService(request.app.state.redis)
    try:
        return await cred_service.rotate(cluster_id, credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "CREDENTIALS_INVALID", "message": str(e)},
        )


@router.post(
    "/clusters/{cluster_id}/credentials/validate",
    response_model=ValidationResult,
    summary="Validate credentials",
    description="Validate stored credentials.",
)
async def validate_credentials(
    request: Request,
    cluster_id: UUID,
):
    """Validate stored credentials.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    cred_service = CredentialService(request.app.state.redis)
    return await cred_service.validate(cluster_id)


@router.delete(
    "/clusters/{cluster_id}/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete credentials",
    description="Delete stored credentials for a cluster.",
)
async def delete_credentials(
    request: Request,
    cluster_id: UUID,
):
    """Delete stored credentials.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    cred_service = CredentialService(request.app.state.redis)
    deleted = await cred_service.delete(cluster_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CREDENTIALS_NOT_FOUND", "message": "No credentials found"},
        )
