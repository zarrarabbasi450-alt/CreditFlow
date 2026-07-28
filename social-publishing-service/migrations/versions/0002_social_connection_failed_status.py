"""allow failed status on social_connections

Revision ID: 0002_social_conn_failed
Revises: 0001_social_schema
Create Date: 2026-07-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_social_conn_failed"
down_revision: str | None = "0001_social_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_social_connections_status", "social_connections", schema="social", type_="check")
    op.create_check_constraint(
        "ck_social_connections_status",
        "social_connections",
        "status IN ('pending', 'connected', 'expired', 'revoked', 'failed')",
        schema="social",
    )


def downgrade() -> None:
    op.drop_constraint("ck_social_connections_status", "social_connections", schema="social", type_="check")
    op.create_check_constraint(
        "ck_social_connections_status",
        "social_connections",
        "status IN ('pending', 'connected', 'expired', 'revoked')",
        schema="social",
    )
