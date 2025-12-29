"""Role-Based Access Control (RBAC) Service.

Spec Reference: specs/06-api-gateway.md Section 3.2

Roles:
- admin: Full access to all resources and operations
- operator: Read/write access to clusters and observability, read-only for settings
- viewer: Read-only access to all resources
"""

from enum import Enum

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from shared.observability import get_logger

logger = get_logger(__name__)


class Role(str, Enum):
    """User roles with hierarchical permissions."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    """Fine-grained permissions."""

    # Cluster permissions
    CLUSTER_READ = "cluster:read"
    CLUSTER_WRITE = "cluster:write"
    CLUSTER_DELETE = "cluster:delete"

    # Observability permissions
    METRICS_READ = "metrics:read"
    LOGS_READ = "logs:read"
    TRACES_READ = "traces:read"
    ALERTS_READ = "alerts:read"
    ALERTS_WRITE = "alerts:write"

    # Intelligence permissions
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    ANOMALY_READ = "anomaly:read"
    REPORTS_READ = "reports:read"
    REPORTS_WRITE = "reports:write"

    # Admin permissions
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),  # All permissions
    Role.OPERATOR: {
        Permission.CLUSTER_READ,
        Permission.CLUSTER_WRITE,
        Permission.METRICS_READ,
        Permission.LOGS_READ,
        Permission.TRACES_READ,
        Permission.ALERTS_READ,
        Permission.ALERTS_WRITE,
        Permission.CHAT_READ,
        Permission.CHAT_WRITE,
        Permission.ANOMALY_READ,
        Permission.REPORTS_READ,
        Permission.REPORTS_WRITE,
        Permission.SETTINGS_READ,
    },
    Role.VIEWER: {
        Permission.CLUSTER_READ,
        Permission.METRICS_READ,
        Permission.LOGS_READ,
        Permission.TRACES_READ,
        Permission.ALERTS_READ,
        Permission.CHAT_READ,
        Permission.ANOMALY_READ,
        Permission.REPORTS_READ,
        Permission.SETTINGS_READ,
    },
}

# OpenShift group to role mapping
GROUP_ROLE_MAPPING: dict[str, Role] = {
    "cluster-admins": Role.ADMIN,
    "aiops-admins": Role.ADMIN,
    "aiops-operators": Role.OPERATOR,
    "aiops-viewers": Role.VIEWER,
}


class UserContext(BaseModel):
    """User context with resolved role and permissions."""

    user_id: str
    username: str
    email: str | None = None
    groups: list[str]
    role: Role
    permissions: set[Permission]

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class RBACService:
    """RBAC authorization service."""

    def resolve_role(self, groups: list[str]) -> Role:
        """Resolve user role from OpenShift groups.

        Returns the highest privilege role matched from user groups.
        Defaults to VIEWER if no matching group found.
        """
        resolved_role = Role.VIEWER

        # Priority order: ADMIN > OPERATOR > VIEWER
        role_priority = {Role.ADMIN: 3, Role.OPERATOR: 2, Role.VIEWER: 1}

        for group in groups:
            if group in GROUP_ROLE_MAPPING:
                mapped_role = GROUP_ROLE_MAPPING[group]
                if role_priority[mapped_role] > role_priority[resolved_role]:
                    resolved_role = mapped_role

        return resolved_role

    def get_permissions(self, role: Role) -> set[Permission]:
        """Get permissions for a role."""
        return ROLE_PERMISSIONS.get(role, set())

    def build_user_context(
        self,
        user_id: str,
        username: str,
        groups: list[str],
        email: str | None = None,
    ) -> UserContext:
        """Build complete user context with resolved permissions."""
        role = self.resolve_role(groups)
        permissions = self.get_permissions(role)

        return UserContext(
            user_id=user_id,
            username=username,
            email=email,
            groups=groups,
            role=role,
            permissions=permissions,
        )

    def check_permission(
        self,
        user_context: UserContext,
        required_permission: Permission,
    ) -> bool:
        """Check if user has required permission."""
        return required_permission in user_context.permissions

    def require_permission(
        self,
        user_context: UserContext,
        required_permission: Permission,
    ) -> None:
        """Require permission or raise 403 Forbidden."""
        if not self.check_permission(user_context, required_permission):
            logger.warning(
                "Permission denied",
                user_id=user_context.user_id,
                required=required_permission.value,
                role=user_context.role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {required_permission.value}",
            )

    def require_any_permission(
        self,
        user_context: UserContext,
        required_permissions: list[Permission],
    ) -> None:
        """Require any of the listed permissions or raise 403."""
        for perm in required_permissions:
            if self.check_permission(user_context, perm):
                return

        logger.warning(
            "Permission denied (none matched)",
            user_id=user_context.user_id,
            required=[p.value for p in required_permissions],
            role=user_context.role.value,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    def require_role(
        self,
        user_context: UserContext,
        minimum_role: Role,
    ) -> None:
        """Require minimum role level or raise 403."""
        role_priority = {Role.ADMIN: 3, Role.OPERATOR: 2, Role.VIEWER: 1}

        if role_priority[user_context.role] < role_priority[minimum_role]:
            logger.warning(
                "Insufficient role",
                user_id=user_context.user_id,
                current_role=user_context.role.value,
                required_role=minimum_role.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher",
            )


# Singleton instance
rbac_service = RBACService()


def get_user_context(request: Request) -> UserContext:
    """Dependency to get user context from request state."""
    if not hasattr(request.state, "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = request.state.user
    return rbac_service.build_user_context(
        user_id=user.sub,
        username=user.preferred_username,
        email=user.email,
        groups=user.groups,
    )


def require_permission(permission: Permission):
    """Decorator factory for requiring a specific permission."""

    def dependency(request: Request) -> UserContext:
        user_context = get_user_context(request)
        rbac_service.require_permission(user_context, permission)
        return user_context

    return dependency


def require_role(minimum_role: Role):
    """Decorator factory for requiring a minimum role."""

    def dependency(request: Request) -> UserContext:
        user_context = get_user_context(request)
        rbac_service.require_role(user_context, minimum_role)
        return user_context

    return dependency
