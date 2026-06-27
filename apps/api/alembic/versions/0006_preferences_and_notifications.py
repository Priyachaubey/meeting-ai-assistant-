"""add preferred_language to users, add notifications table"""
from alembic import op
import sqlalchemy as sa

revision = "0006_preferences_and_notifications"
down_revision = "0005_workspaces"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("preferred_language", sa.String(), nullable=False, server_default="en"))

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("meeting_id", sa.String(), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade():
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_column("users", "preferred_language")
