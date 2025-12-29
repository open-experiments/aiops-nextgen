"""Tests for RBAC service."""

import pytest
from app.services.rbac import (
    Permission,
    RBACService,
    Role,
)
from fastapi import HTTPException


@pytest.fixture
def rbac_service():
    return RBACService()


class TestRoleResolution:
    def test_admin_group_resolves_to_admin(self, rbac_service):
        """Test cluster-admins group resolves to admin role."""
        groups = ["cluster-admins"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.ADMIN

    def test_aiops_admin_group_resolves_to_admin(self, rbac_service):
        """Test aiops-admins group resolves to admin role."""
        groups = ["aiops-admins"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.ADMIN

    def test_operator_group_resolves_to_operator(self, rbac_service):
        """Test aiops-operators group resolves to operator role."""
        groups = ["aiops-operators"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.OPERATOR

    def test_viewer_group_resolves_to_viewer(self, rbac_service):
        """Test aiops-viewers group resolves to viewer role."""
        groups = ["aiops-viewers"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.VIEWER

    def test_unknown_group_defaults_to_viewer(self, rbac_service):
        """Test unknown groups default to viewer role."""
        groups = ["unknown-group", "another-unknown"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.VIEWER

    def test_highest_role_wins(self, rbac_service):
        """Test highest privilege role is selected when multiple match."""
        groups = ["aiops-viewers", "aiops-operators", "cluster-admins"]
        role = rbac_service.resolve_role(groups)
        assert role == Role.ADMIN

    def test_empty_groups_defaults_to_viewer(self, rbac_service):
        """Test empty groups list defaults to viewer."""
        groups = []
        role = rbac_service.resolve_role(groups)
        assert role == Role.VIEWER


class TestPermissions:
    def test_admin_has_all_permissions(self, rbac_service):
        """Test admin role has all permissions."""
        permissions = rbac_service.get_permissions(Role.ADMIN)
        assert Permission.CLUSTER_DELETE in permissions
        assert Permission.USERS_WRITE in permissions
        assert Permission.SETTINGS_WRITE in permissions

    def test_operator_cannot_delete_clusters(self, rbac_service):
        """Test operator role cannot delete clusters."""
        permissions = rbac_service.get_permissions(Role.OPERATOR)
        assert Permission.CLUSTER_DELETE not in permissions
        assert Permission.CLUSTER_WRITE in permissions

    def test_operator_cannot_write_users(self, rbac_service):
        """Test operator role cannot write users."""
        permissions = rbac_service.get_permissions(Role.OPERATOR)
        assert Permission.USERS_WRITE not in permissions
        assert Permission.USERS_READ not in permissions

    def test_viewer_is_read_only(self, rbac_service):
        """Test viewer role has only read permissions."""
        permissions = rbac_service.get_permissions(Role.VIEWER)

        for perm in permissions:
            assert "write" not in perm.value
            assert "delete" not in perm.value


class TestPermissionChecks:
    @pytest.fixture
    def admin_context(self, rbac_service):
        return rbac_service.build_user_context(
            user_id="admin-1",
            username="admin",
            groups=["cluster-admins"],
        )

    @pytest.fixture
    def operator_context(self, rbac_service):
        return rbac_service.build_user_context(
            user_id="operator-1",
            username="operator",
            groups=["aiops-operators"],
        )

    @pytest.fixture
    def viewer_context(self, rbac_service):
        return rbac_service.build_user_context(
            user_id="viewer-1",
            username="viewer",
            groups=["aiops-viewers"],
        )

    def test_require_permission_success(self, rbac_service, admin_context):
        """Test require_permission passes for authorized user."""
        # Should not raise
        rbac_service.require_permission(admin_context, Permission.CLUSTER_DELETE)

    def test_require_permission_failure(self, rbac_service, viewer_context):
        """Test require_permission raises for unauthorized user."""
        with pytest.raises(HTTPException) as exc_info:
            rbac_service.require_permission(viewer_context, Permission.CLUSTER_WRITE)

        assert exc_info.value.status_code == 403

    def test_require_role_success(self, rbac_service, admin_context):
        """Test require_role passes for sufficient role."""
        rbac_service.require_role(admin_context, Role.OPERATOR)

    def test_require_role_failure(self, rbac_service, viewer_context):
        """Test require_role raises for insufficient role."""
        with pytest.raises(HTTPException) as exc_info:
            rbac_service.require_role(viewer_context, Role.OPERATOR)

        assert exc_info.value.status_code == 403

    def test_require_any_permission_success(self, rbac_service, operator_context):
        """Test require_any_permission passes when one matches."""
        rbac_service.require_any_permission(
            operator_context,
            [Permission.CLUSTER_DELETE, Permission.CLUSTER_WRITE],
        )

    def test_require_any_permission_failure(self, rbac_service, viewer_context):
        """Test require_any_permission fails when none match."""
        with pytest.raises(HTTPException) as exc_info:
            rbac_service.require_any_permission(
                viewer_context,
                [Permission.CLUSTER_DELETE, Permission.CLUSTER_WRITE],
            )

        assert exc_info.value.status_code == 403


class TestUserContext:
    def test_build_user_context(self, rbac_service):
        """Test building complete user context."""
        context = rbac_service.build_user_context(
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            groups=["aiops-operators"],
        )

        assert context.user_id == "user-123"
        assert context.role == Role.OPERATOR
        assert Permission.CLUSTER_WRITE in context.permissions
        assert Permission.CLUSTER_DELETE not in context.permissions

    def test_build_user_context_without_email(self, rbac_service):
        """Test building user context without email."""
        context = rbac_service.build_user_context(
            user_id="user-123",
            username="testuser",
            groups=["aiops-viewers"],
        )

        assert context.email is None
        assert context.role == Role.VIEWER
