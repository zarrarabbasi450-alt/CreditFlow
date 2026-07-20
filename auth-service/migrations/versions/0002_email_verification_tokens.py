"""Add secure email verification tokens."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_email_verification_tokens"
down_revision: str | None = "0001_auth_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        schema="auth",
    )
    op.create_index(
        "ix_auth_email_verification_tokens_user_id",
        "email_verification_tokens",
        ["user_id"],
        schema="auth",
    )
    op.create_index(
        "ix_auth_email_verification_tokens_expires_at",
        "email_verification_tokens",
        ["expires_at"],
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("email_verification_tokens", schema="auth")
