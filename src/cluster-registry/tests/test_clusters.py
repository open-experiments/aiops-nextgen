"""Tests for Cluster CRUD API.

Spec Reference: specs/02-cluster-registry.md Section 4.1
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(test_client: AsyncClient):
    """Test health endpoint returns healthy status."""
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_cluster(test_client: AsyncClient, sample_cluster_data):
    """Test creating a new cluster.

    Spec Reference: specs/02-cluster-registry.md Section 4.1, 4.2
    """
    response = await test_client.post("/api/v1/clusters", json=sample_cluster_data)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == sample_cluster_data["name"]
    assert data["display_name"] == sample_cluster_data["display_name"]
    assert data["api_server_url"] == sample_cluster_data["api_server_url"]
    assert data["cluster_type"] == sample_cluster_data["cluster_type"]
    assert "id" in data


@pytest.mark.asyncio
async def test_create_cluster_duplicate_name(
    test_client: AsyncClient, sample_cluster_data
):
    """Test creating cluster with duplicate name returns 409.

    Spec Reference: specs/02-cluster-registry.md Section 12
    """
    # Create first cluster
    response = await test_client.post("/api/v1/clusters", json=sample_cluster_data)
    assert response.status_code == 201

    # Try to create duplicate
    response = await test_client.post("/api/v1/clusters", json=sample_cluster_data)
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "CLUSTER_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_create_cluster_invalid_name(test_client: AsyncClient, sample_cluster_data):
    """Test creating cluster with invalid name returns 422.

    Spec Reference: specs/02-cluster-registry.md Section 7.1
    """
    sample_cluster_data["name"] = "INVALID_NAME"  # Not DNS-compatible
    response = await test_client.post("/api/v1/clusters", json=sample_cluster_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_cluster_by_id(test_client: AsyncClient, sample_cluster_data):
    """Test getting cluster by ID.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    # Create cluster
    create_response = await test_client.post("/api/v1/clusters", json=sample_cluster_data)
    cluster_id = create_response.json()["id"]

    # Get cluster
    response = await test_client.get(f"/api/v1/clusters/{cluster_id}")
    assert response.status_code == 200
    assert response.json()["id"] == cluster_id
    assert response.json()["name"] == sample_cluster_data["name"]


@pytest.mark.asyncio
async def test_get_cluster_not_found(test_client: AsyncClient):
    """Test getting non-existent cluster returns 404.

    Spec Reference: specs/02-cluster-registry.md Section 12
    """
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await test_client.get(f"/api/v1/clusters/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "CLUSTER_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_clusters(test_client: AsyncClient, sample_cluster_data):
    """Test listing clusters.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    # Create cluster
    await test_client.post("/api/v1/clusters", json=sample_cluster_data)

    # List clusters
    response = await test_client.get("/api/v1/clusters")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_clusters_with_filters(test_client: AsyncClient, sample_cluster_data):
    """Test listing clusters with filters.

    Spec Reference: specs/02-cluster-registry.md Section 4.3
    """
    # Create cluster
    await test_client.post("/api/v1/clusters", json=sample_cluster_data)

    # Filter by environment
    response = await test_client.get(
        "/api/v1/clusters", params={"environment": "DEVELOPMENT"}
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1

    # Filter by non-matching environment
    response = await test_client.get(
        "/api/v1/clusters", params={"environment": "PRODUCTION"}
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_update_cluster(test_client: AsyncClient, sample_cluster_data):
    """Test updating cluster.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    # Create cluster
    create_response = await test_client.post("/api/v1/clusters", json=sample_cluster_data)
    cluster_id = create_response.json()["id"]

    # Update cluster
    update_data = {"display_name": "Updated Display Name", "region": "us-west-2"}
    response = await test_client.put(f"/api/v1/clusters/{cluster_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Display Name"
    assert response.json()["region"] == "us-west-2"


@pytest.mark.asyncio
async def test_delete_cluster(test_client: AsyncClient, sample_cluster_data):
    """Test deleting cluster.

    Spec Reference: specs/02-cluster-registry.md Section 4.1
    """
    # Create cluster
    create_response = await test_client.post("/api/v1/clusters", json=sample_cluster_data)
    cluster_id = create_response.json()["id"]

    # Delete cluster
    response = await test_client.delete(f"/api/v1/clusters/{cluster_id}")
    assert response.status_code == 204

    # Verify deleted
    response = await test_client.get(f"/api/v1/clusters/{cluster_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_fleet_summary(test_client: AsyncClient, sample_cluster_data):
    """Test fleet summary endpoint.

    Spec Reference: specs/02-cluster-registry.md Section 4.2
    """
    # Create cluster
    await test_client.post("/api/v1/clusters", json=sample_cluster_data)

    # Get fleet summary
    response = await test_client.get("/api/v1/fleet/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["total_clusters"] >= 1
    assert "by_state" in data
    assert "by_type" in data
    assert "by_environment" in data
