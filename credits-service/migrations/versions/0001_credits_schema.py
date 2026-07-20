"""Create the Credits Service-owned schema and append-only ledger."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_credits_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS credits")
    ledger_type = postgresql.ENUM(
        "grant",
        "usage",
        "trade",
        "refund_clawback",
        "adjustment",
        name="ledger_type",
        schema="credits",
        create_type=False,
    )
    listing_status = postgresql.ENUM(
        "open",
        "reserved",
        "sold",
        "canceled",
        "expired",
        name="listing_status",
        schema="credits",
        create_type=False,
    )
    ledger_type.create(op.get_bind(), checkfirst=True)
    listing_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "credits_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", ledger_type, nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("reference_type", sa.String(64), nullable=False),
        sa.Column("reference_id", sa.String(255), nullable=False),
        sa.Column("counterparty_account_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount <> 0", name="ck_credits_ledger_nonzero_amount"),
        schema="credits",
    )
    op.create_index(
        "ix_credits_ledger_account_created", "credits_ledger", ["account_id", "created_at"], schema="credits"
    )
    op.create_index("ix_credits_ledger_reference_id", "credits_ledger", ["reference_id"], schema="credits")
    op.create_table(
        "marketplace_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credits", sa.BigInteger(), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("status", listing_status, nullable=False),
        sa.Column("buyer_account_id", postgresql.UUID(as_uuid=True)),
        sa.Column("payment_intent_id", sa.String(255), unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("credits > 0", name="ck_marketplace_positive_credits"),
        sa.CheckConstraint("price_cents > 0", name="ck_marketplace_positive_price"),
        schema="credits",
    )
    op.create_index(
        "ix_marketplace_status_expires", "marketplace_listings", ["status", "expires_at"], schema="credits"
    )
    op.create_table(
        "processed_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        schema="credits",
    )
    op.create_index("ix_credits_processed_event_type", "processed_events", ["event_type"], schema="credits")
    op.execute("""
        CREATE FUNCTION credits.reject_ledger_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'credits_ledger is append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER credits_ledger_append_only
        BEFORE UPDATE OR DELETE ON credits.credits_ledger
        FOR EACH ROW EXECUTE FUNCTION credits.reject_ledger_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS credits_ledger_append_only ON credits.credits_ledger")
    op.execute("DROP FUNCTION IF EXISTS credits.reject_ledger_mutation")
    op.drop_table("processed_events", schema="credits")
    op.drop_table("marketplace_listings", schema="credits")
    op.drop_table("credits_ledger", schema="credits")
    postgresql.ENUM(name="listing_status", schema="credits").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ledger_type", schema="credits").drop(op.get_bind(), checkfirst=True)
