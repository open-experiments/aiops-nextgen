"""Cluster data access repository.

Spec Reference: specs/02-cluster-registry.md Section 7
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, and_, or_, Integer, literal_column, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models import ClusterModel, ClusterHealthHistoryModel
from ..schemas.cluster import ClusterFilters


class ClusterRepository:
    """Repository for cluster data access.

    Spec Reference: specs/02-cluster-registry.md Section 7.1
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict[str, Any]) -> ClusterModel:
        """Create a new cluster.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        cluster = ClusterModel(**data)
        self.session.add(cluster)
        await self.session.commit()
        await self.session.refresh(cluster)
        return cluster

    async def get_by_id(self, cluster_id: UUID) -> ClusterModel | None:
        """Get cluster by ID.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        result = await self.session.execute(
            select(ClusterModel).where(ClusterModel.id == cluster_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> ClusterModel | None:
        """Get cluster by name.

        Spec Reference: specs/02-cluster-registry.md Section 4.1
        """
        result = await self.session.execute(
            select(ClusterModel).where(ClusterModel.name == name)
        )
        return result.scalar_one_or_none()

    async def list(
        self, filters: ClusterFilters
    ) -> tuple[list[ClusterModel], int]:
        """List clusters with filtering and pagination.

        Spec Reference: specs/02-cluster-registry.md Section 4.3
        """
        query = select(ClusterModel)
        conditions = []

        # Apply filters
        if filters.name:
            conditions.append(ClusterModel.name.ilike(f"%{filters.name}%"))
        if filters.cluster_type:
            conditions.append(ClusterModel.cluster_type == filters.cluster_type.value)
        if filters.environment:
            conditions.append(ClusterModel.environment == filters.environment.value)
        if filters.region:
            conditions.append(ClusterModel.region == filters.region)
        if filters.state:
            conditions.append(
                ClusterModel.status["state"].astext == filters.state.value
            )
        if filters.has_gpu is not None:
            if filters.has_gpu:
                conditions.append(
                    ClusterModel.capabilities["has_gpu_nodes"].astext == "true"
                )
            else:
                conditions.append(
                    or_(
                        ClusterModel.capabilities["has_gpu_nodes"].astext == "false",
                        ClusterModel.capabilities.is_(None),
                    )
                )
        if filters.has_cnf is not None:
            if filters.has_cnf:
                conditions.append(
                    ClusterModel.capabilities["has_cnf_workloads"].astext == "true"
                )
            else:
                conditions.append(
                    or_(
                        ClusterModel.capabilities["has_cnf_workloads"].astext == "false",
                        ClusterModel.capabilities.is_(None),
                    )
                )
        if filters.label:
            # Parse label=key=value format
            if "=" in filters.label:
                key, value = filters.label.split("=", 1)
                conditions.append(ClusterModel.labels[key].astext == value)

        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)
        query = query.order_by(ClusterModel.name)

        result = await self.session.execute(query)
        clusters = list(result.scalars().all())

        return clusters, total

    async def update(
        self, cluster_id: UUID, data: dict[str, Any]
    ) -> ClusterModel | None:
        """Update a cluster.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        cluster = await self.get_by_id(cluster_id)
        if not cluster:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(cluster, key, value)

        cluster.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(cluster)
        return cluster

    async def delete(self, cluster_id: UUID) -> bool:
        """Delete a cluster.

        Spec Reference: specs/02-cluster-registry.md Section 5.1
        """
        cluster = await self.get_by_id(cluster_id)
        if not cluster:
            return False

        await self.session.delete(cluster)
        await self.session.commit()
        return True

    async def update_status(
        self, cluster_id: UUID, status: dict[str, Any]
    ) -> ClusterModel | None:
        """Update cluster status.

        Spec Reference: specs/02-cluster-registry.md Section 5.4
        """
        cluster = await self.get_by_id(cluster_id)
        if not cluster:
            return None

        cluster.status = status
        cluster.last_seen_at = datetime.utcnow()
        cluster.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(cluster)
        return cluster

    async def update_capabilities(
        self, cluster_id: UUID, capabilities: dict[str, Any]
    ) -> ClusterModel | None:
        """Update cluster capabilities.

        Spec Reference: specs/02-cluster-registry.md Section 5.3
        """
        cluster = await self.get_by_id(cluster_id)
        if not cluster:
            return None

        cluster.capabilities = capabilities
        cluster.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(cluster)
        return cluster

    async def add_health_history(
        self, cluster_id: UUID, status: dict[str, Any]
    ) -> ClusterHealthHistoryModel:
        """Add health check history entry.

        Spec Reference: specs/02-cluster-registry.md Section 7.1
        """
        history = ClusterHealthHistoryModel(
            cluster_id=cluster_id,
            status=status,
        )
        self.session.add(history)
        await self.session.commit()
        return history

    async def get_all_clusters(self) -> list[ClusterModel]:
        """Get all clusters for background tasks."""
        result = await self.session.execute(select(ClusterModel))
        return list(result.scalars().all())

    async def get_fleet_summary(self) -> dict[str, Any]:
        """Get fleet summary statistics.

        Spec Reference: specs/02-cluster-registry.md Section 4.2 - Fleet Summary
        """
        # Total clusters
        total_result = await self.session.execute(
            select(func.count()).select_from(ClusterModel)
        )
        total = total_result.scalar() or 0

        # By state - use raw SQL to avoid SQLAlchemy JSONB GROUP BY issues
        state_result = await self.session.execute(
            text("""
                SELECT status->>'state' as state, count(*) as count
                FROM clusters.clusters
                GROUP BY status->>'state'
            """)
        )
        by_state = {row.state: row.count for row in state_result}

        # By type
        type_result = await self.session.execute(
            select(
                ClusterModel.cluster_type,
                func.count().label("count"),
            ).group_by(ClusterModel.cluster_type)
        )
        by_type = {row.cluster_type: row.count for row in type_result}

        # By environment
        env_result = await self.session.execute(
            select(
                ClusterModel.environment,
                func.count().label("count"),
            ).group_by(ClusterModel.environment)
        )
        by_environment = {row.environment: row.count for row in env_result}

        # GPU count - use raw SQL
        gpu_result = await self.session.execute(
            text("""
                SELECT COALESCE(SUM((capabilities->>'gpu_count')::int), 0) as total
                FROM clusters.clusters
                WHERE capabilities IS NOT NULL
            """)
        )
        total_gpu = gpu_result.scalar() or 0

        # CNF clusters
        cnf_result = await self.session.execute(
            text("""
                SELECT count(*) as count
                FROM clusters.clusters
                WHERE capabilities->>'has_cnf_workloads' = 'true'
            """)
        )
        clusters_with_cnf = cnf_result.scalar() or 0

        # Average health score
        health_result = await self.session.execute(
            text("""
                SELECT COALESCE(AVG((status->>'health_score')::int), 0) as avg
                FROM clusters.clusters
            """)
        )
        avg_health = health_result.scalar() or 0.0

        return {
            "total_clusters": total,
            "by_state": by_state,
            "by_type": by_type,
            "by_environment": by_environment,
            "total_gpu_count": int(total_gpu),
            "clusters_with_cnf": int(clusters_with_cnf),
            "avg_health_score": float(avg_health),
        }
