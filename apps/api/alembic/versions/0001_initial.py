"""initial schema"""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("users", sa.Column("id", sa.String(), primary_key=True), sa.Column("email", sa.String(), nullable=False), sa.Column("hashed_password", sa.String(), nullable=False), sa.Column("role", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime()))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("meetings", sa.Column("id", sa.String(), primary_key=True), sa.Column("title", sa.String()), sa.Column("mode", sa.String()), sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id")), sa.Column("encrypted", sa.Boolean()), sa.Column("summary", sa.Text()), sa.Column("intelligence", sa.JSON()), sa.Column("created_at", sa.DateTime()))
    op.create_table("transcript_events", sa.Column("id", sa.String(), primary_key=True), sa.Column("meeting_id", sa.String(), sa.ForeignKey("meetings.id")), sa.Column("speaker", sa.String()), sa.Column("text", sa.Text()), sa.Column("kind", sa.String()), sa.Column("timestamp_ms", sa.Integer()))
    op.create_table("documents", sa.Column("id", sa.String(), primary_key=True), sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id")), sa.Column("filename", sa.String()), sa.Column("content_type", sa.String()), sa.Column("qdrant_collection", sa.String()), sa.Column("created_at", sa.DateTime()))
def downgrade():
    op.drop_table("documents")
    op.drop_table("transcript_events")
    op.drop_table("meetings")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
