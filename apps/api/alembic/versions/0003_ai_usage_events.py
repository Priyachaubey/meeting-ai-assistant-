"""add ai_usage_events table"""
from alembic import op
import sqlalchemy as sa

revision = "0003_ai_usage_events"
down_revision = "0002_billing_and_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("meeting_id", sa.String(), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_usage_events_owner_id", "ai_usage_events", ["owner_id"])
    op.create_index("ix_ai_usage_events_meeting_id", "ai_usage_events", ["meeting_id"])
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])


def downgrade():
    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_meeting_id", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_owner_id", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
