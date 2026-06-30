"""add audio_capture_mode to users"""
from alembic import op
import sqlalchemy as sa

revision = "0004_user_preferences"
down_revision = "0003_ai_usage_events"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("audio_capture_mode", sa.String(), nullable=False, server_default="hybrid"),
    )


def downgrade():
    op.drop_column("users", "audio_capture_mode")
