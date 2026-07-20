"""Add the optional platform-level SuperAdmin role."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_platform_role"
down_revision: str | None = "0002_email_verification_tokens"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("platform_role", sa.String(32)), schema="auth")
    op.create_check_constraint(
        "ck_auth_users_platform_role",
        "users",
        "platform_role IS NULL OR platform_role = 'SuperAdmin'",
        schema="auth",
    )
    op.create_index("ix_auth_users_platform_role", "users", ["platform_role"], schema="auth")


def downgrade() -> None:
    op.drop_index("ix_auth_users_platform_role", table_name="users", schema="auth")
    op.drop_constraint("ck_auth_users_platform_role", "users", schema="auth", type_="check")
    op.drop_column("users", "platform_role", schema="auth")
