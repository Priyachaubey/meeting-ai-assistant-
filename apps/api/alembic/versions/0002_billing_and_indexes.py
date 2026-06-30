"""add full_name, FK indexes, subscriptions table"""
from alembic import op
import sqlalchemy as sa

revision = "0002_billing_and_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))

    # Every FK below was unindexed in 0001 — fine at zero rows, painful once
    # meetings/transcript_events grow. Cheap to add now, expensive to add later
    # under load (full table lock on most engines without CONCURRENTLY, which
    # alembic's autogenerate doesn't do for you).
    op.create_index("ix_meetings_owner_id", "meetings", ["owner_id"])
    op.create_index("ix_transcript_events_meeting_id", "transcript_events", ["meeting_id"])
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("status", sa.String(), nullable=False, server_default="inactive"),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_subscriptions_owner_id", "subscriptions", ["owner_id"])
    op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"])
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])


def downgrade():
    op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_stripe_customer_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_owner_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_documents_owner_id", table_name="documents")
    op.drop_index("ix_transcript_events_meeting_id", table_name="transcript_events")
    op.drop_index("ix_meetings_owner_id", table_name="meetings")
    op.drop_column("users", "full_name")
