"""Add secure account invitations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_invites"
down_revision: str | None = "0002_accounts_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_tenant_invites_role"),
        sa.ForeignKeyConstraint(["account_id"], ["tenant.accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        schema="tenant",
    )
    op.create_index("ix_tenant_invites_account_id", "invites", ["account_id"], schema="tenant")
    op.create_index("ix_tenant_invites_expires_at", "invites", ["expires_at"], schema="tenant")
    op.create_index("ix_tenant_invites_account_email", "invites", ["account_id", "email"], schema="tenant")


def downgrade() -> None:
    op.drop_table("invites", schema="tenant")
