"""rework documents table: workspace scoping + storage fields

The documents table has existed since migration 0001 but no row was ever written to it (
uploads were processed in-memory and discarded — see AUDIT.md). Safe to alter directly
rather than write a data-migrating one: there's no data to migrate.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_documents_storage"
down_revision = "0007_share_links"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite: owner_id column ko abhi drop mat karo
    # op.drop_index("ix_documents_owner_id", table_name="documents")
    # op.drop_column("documents", "owner_id")

    op.add_column("documents", sa.Column("workspace_id", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("uploaded_by", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("storage_key", sa.String(), nullable=False, server_default=""))
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])


def downgrade():
    op.drop_index("ix_documents_workspace_id", table_name="documents")
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "uploaded_by")
    op.drop_column("documents", "workspace_id")
    op.add_column("documents", sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id"), nullable=False))
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
