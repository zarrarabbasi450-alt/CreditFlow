"""create ai generation schema"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_ai_generation_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ai_generation")
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_microusd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("prompt_tokens >= 0", name="ck_generation_prompt_tokens_nonnegative"),
        sa.CheckConstraint("completion_tokens >= 0", name="ck_generation_completion_tokens_nonnegative"),
        sa.CheckConstraint("total_tokens >= 0", name="ck_generation_total_tokens_nonnegative"),
        sa.CheckConstraint("cost_microusd >= 0", name="ck_generation_cost_nonnegative"),
        schema="ai_generation",
    )
    op.create_index(
        "ix_generation_jobs_account_created",
        "generation_jobs",
        ["account_id", "created_at"],
        schema="ai_generation",
    )
    op.create_index(
        "ix_generation_jobs_account_status",
        "generation_jobs",
        ["account_id", "status"],
        schema="ai_generation",
    )
    op.create_table(
        "prompt_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_id"], ["ai_generation.generation_jobs.id"], ondelete="CASCADE"),
        schema="ai_generation",
    )
    op.create_index(
        "ix_prompt_history_account_created",
        "prompt_history",
        ["account_id", "created_at"],
        schema="ai_generation",
    )
    op.create_table(
        "image_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="ai_generation",
    )
    op.create_index(
        "ix_image_generation_account_created",
        "image_generation_jobs",
        ["account_id", "created_at"],
        schema="ai_generation",
    )


def downgrade() -> None:
    op.drop_table("image_generation_jobs", schema="ai_generation")
    op.drop_table("prompt_history", schema="ai_generation")
    op.drop_table("generation_jobs", schema="ai_generation")
    op.execute("DROP SCHEMA IF EXISTS ai_generation")
