"""Create the append-only Usage Service ledger."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_usage_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS usage")
    op.create_table(
        "usage_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("prompt_tokens >= 0", name="ck_usage_prompt_tokens_nonnegative"),
        sa.CheckConstraint("completion_tokens >= 0", name="ck_usage_completion_tokens_nonnegative"),
        sa.CheckConstraint("total_tokens > 0", name="ck_usage_total_tokens_positive"),
        sa.CheckConstraint("cost_microusd >= 0", name="ck_usage_cost_nonnegative"),
        schema="usage",
    )
    op.create_index(
        "ix_usage_ledger_account_created", "usage_ledger", ["account_id", "created_at"], schema="usage"
    )
    op.create_index("ix_usage_ledger_account_model", "usage_ledger", ["account_id", "model"], schema="usage")
    op.create_index("ix_usage_ledger_user_id", "usage_ledger", ["user_id"], schema="usage")
    op.execute("""
        CREATE FUNCTION usage.reject_ledger_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'usage_ledger is append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER usage_ledger_append_only
        BEFORE UPDATE OR DELETE ON usage.usage_ledger
        FOR EACH ROW EXECUTE FUNCTION usage.reject_ledger_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS usage_ledger_append_only ON usage.usage_ledger")
    op.execute("DROP FUNCTION IF EXISTS usage.reject_ledger_mutation")
    op.drop_table("usage_ledger", schema="usage")
