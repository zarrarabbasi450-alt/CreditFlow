"""Extend accounts and add account membership."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_accounts_membership"
down_revision: str | None = "0001_tenant_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("type", sa.String(length=32), server_default="individual", nullable=False),
        schema="tenant",
    )
    op.add_column(
        "accounts",
        sa.Column("plan_tier", sa.String(length=32), server_default="free", nullable=False),
        schema="tenant",
    )
    op.add_column(
        "accounts",
        sa.Column("seat_count", sa.Integer(), server_default="1", nullable=False),
        schema="tenant",
    )
    op.create_check_constraint(
        "ck_tenant_accounts_type", "accounts", "type IN ('individual', 'team')", schema="tenant"
    )
    op.create_check_constraint(
        "ck_tenant_accounts_seat_count", "accounts", "seat_count >= 1", schema="tenant"
    )
    op.create_table(
        "account_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="member", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_tenant_account_members_role"),
        sa.ForeignKeyConstraint(["account_id"], ["tenant.accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "user_id", name="uq_tenant_account_members_account_user"),
        schema="tenant",
    )
    op.create_index(
        "ix_tenant_account_members_account_id", "account_members", ["account_id"], schema="tenant"
    )
    op.create_index("ix_tenant_account_members_user_id", "account_members", ["user_id"], schema="tenant")
    op.create_index(
        "ix_tenant_account_members_account_role",
        "account_members",
        ["account_id", "role"],
        schema="tenant",
    )


def downgrade() -> None:
    op.drop_table("account_members", schema="tenant")
    op.drop_constraint("ck_tenant_accounts_seat_count", "accounts", schema="tenant", type_="check")
    op.drop_constraint("ck_tenant_accounts_type", "accounts", schema="tenant", type_="check")
    op.drop_column("accounts", "seat_count", schema="tenant")
    op.drop_column("accounts", "plan_tier", schema="tenant")
    op.drop_column("accounts", "type", schema="tenant")
