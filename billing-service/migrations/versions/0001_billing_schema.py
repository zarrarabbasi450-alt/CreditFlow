"""Create billing schema and owned tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_billing_schema"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS billing")
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("stripe_subscription_item_id", sa.String(255)),
        sa.Column("plan", sa.String(32), nullable=False, server_default="free"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("seats", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("plan IN ('free','pro','team')", name="ck_billing_subscription_plan"),
        sa.UniqueConstraint("account_id"),
        sa.UniqueConstraint("stripe_customer_id"),
        sa.UniqueConstraint("stripe_subscription_id"),
        schema="billing",
    )
    for column in ("account_id", "stripe_customer_id", "stripe_subscription_id", "grace_period_ends_at"):
        op.create_index(f"ix_billing_subscriptions_{column}", "subscriptions", [column], schema="billing")
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(255), nullable=False, unique=True),
        sa.Column("number", sa.String(100)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount_due", sa.BigInteger(), nullable=False),
        sa.Column("amount_paid", sa.BigInteger(), nullable=False),
        sa.Column("payment_intent_id", sa.String(255)),
        sa.Column("hosted_invoice_url", sa.Text()),
        sa.Column("invoice_pdf", sa.Text()),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="billing",
    )
    op.create_index("ix_billing_invoices_account_id", "invoices", ["account_id"], schema="billing")
    op.create_index(
        "ix_billing_invoices_payment_intent_id", "invoices", ["payment_intent_id"], schema="billing"
    )
    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_event_id", sa.String(255), nullable=False, unique=True),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="billing",
    )
    op.create_index(
        "ix_billing_subscription_events_provider_event_id",
        "subscription_events",
        ["provider_event_id"],
        schema="billing",
    )
    op.create_index(
        "ix_billing_subscription_events_event_type", "subscription_events", ["event_type"], schema="billing"
    )
    op.create_table(
        "refunds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("stripe_refund_id", sa.String(255), nullable=False, unique=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="billing",
    )
    op.create_index("ix_billing_refunds_account_id", "refunds", ["account_id"], schema="billing")
    op.create_index("ix_billing_refunds_invoice_id", "refunds", ["invoice_id"], schema="billing")
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="billing",
    )
    op.create_index("ix_billing_outbox_events_event_type", "outbox_events", ["event_type"], schema="billing")
    op.create_index(
        "ix_billing_outbox_unpublished", "outbox_events", ["published_at", "created_at"], schema="billing"
    )


def downgrade() -> None:
    for table in ("outbox_events", "refunds", "subscription_events", "invoices", "subscriptions"):
        op.drop_table(table, schema="billing")
    op.execute("DROP SCHEMA IF EXISTS billing")
