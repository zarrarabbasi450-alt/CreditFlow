"""unique active content schedule

Revision ID: 0002_sched_unique
Revises: 0001_scheduler_schema
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_sched_unique"
down_revision: str | None = "0001_scheduler_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY account_id, content_id
                    ORDER BY publish_at ASC, created_at ASC, id ASC
                ) AS duplicate_rank
            FROM scheduler.scheduled_posts
            WHERE status = 'scheduled'
        )
        UPDATE scheduler.scheduled_posts AS scheduled_posts
        SET
            status = 'cancelled',
            cancelled_at = now(),
            updated_at = now()
        FROM ranked
        WHERE scheduled_posts.id = ranked.id
          AND ranked.duplicate_rank > 1
        """
    )
    op.create_index(
        "uq_scheduled_posts_active_content",
        "scheduled_posts",
        ["account_id", "content_id"],
        unique=True,
        schema="scheduler",
        postgresql_where=sa.text("status = 'scheduled'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_scheduled_posts_active_content",
        table_name="scheduled_posts",
        schema="scheduler",
    )
