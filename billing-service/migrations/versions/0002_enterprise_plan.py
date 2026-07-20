"""Allow Enterprise billing plans."""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_enterprise_plan"
down_revision: str | None = "0001_billing_schema"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_billing_subscription_plan", "subscriptions", schema="billing", type_="check")
    op.create_check_constraint(
        "ck_billing_subscription_plan",
        "subscriptions",
        "plan IN ('free','pro','team','enterprise')",
        schema="billing",
    )


def downgrade() -> None:
    op.execute("UPDATE billing.subscriptions SET plan = 'team' WHERE plan = 'enterprise'")
    op.drop_constraint("ck_billing_subscription_plan", "subscriptions", schema="billing", type_="check")
    op.create_check_constraint(
        "ck_billing_subscription_plan",
        "subscriptions",
        "plan IN ('free','pro','team')",
        schema="billing",
    )
