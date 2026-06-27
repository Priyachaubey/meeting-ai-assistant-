"""add meeting_share_links and share_link_accesses"""
from alembic import op
import sqlalchemy as sa

revision = "0007_share_links"
down_revision = "0006_preferences_and_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "meeting_share_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("meeting_id", sa.String(), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_meeting_share_links_meeting_id", "meeting_share_links", ["meeting_id"])
    op.create_index("ix_meeting_share_links_token_hash", "meeting_share_links", ["token_hash"])

    op.create_table(
        "share_link_accesses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("link_id", sa.String(), sa.ForeignKey("meeting_share_links.id"), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_share_link_accesses_link_id", "share_link_accesses", ["link_id"])


def downgrade():
    op.drop_index("ix_share_link_accesses_link_id", table_name="share_link_accesses")
    op.drop_table("share_link_accesses")
    op.drop_index("ix_meeting_share_links_token_hash", table_name="meeting_share_links")
    op.drop_index("ix_meeting_share_links_meeting_id", table_name="meeting_share_links")
    op.drop_table("meeting_share_links")
