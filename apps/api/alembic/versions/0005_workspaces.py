"""add workspaces, workspace_memberships, meetings.workspace_id"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0005_workspaces"
down_revision = "0004_user_preferences"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
    )
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"])
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])

    op.add_column(
    "meetings",
    sa.Column("workspace_id", sa.String(), nullable=True)
)
    op.create_index("ix_meetings_workspace_id", "meetings", ["workspace_id"])

    # Backfill: every existing user gets a personal workspace, and every meeting they already
    # own gets assigned to it. Without this, upgrading an existing database would leave every
    # pre-existing meeting with workspace_id = NULL — invisible to the new workspace-scoped
    # list/detail queries even though the data is still there. New users get this same
    # personal-workspace creation at register() time (see routes/auth.py) instead of a
    # migration, since that only runs once per signup, not once at deploy time.
    conn = op.get_bind()
    from datetime import datetime

    users = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    for user_id, email in users:
        workspace_id = str(uuid.uuid4())
        now = datetime.utcnow()
        conn.execute(
            sa.text(
                "INSERT INTO workspaces (id, name, created_by, created_at) "
                "VALUES (:id, :name, :created_by, :created_at)"
            ),
            {"id": workspace_id, "name": f"{email}'s Workspace", "created_by": user_id, "created_at": now},
        )
        conn.execute(
            sa.text(
                "INSERT INTO workspace_memberships (id, workspace_id, user_id, role, joined_at) "
                "VALUES (:id, :workspace_id, :user_id, 'owner', :joined_at)"
            ),
            {"id": str(uuid.uuid4()), "workspace_id": workspace_id, "user_id": user_id, "joined_at": now},
        )
        conn.execute(
            sa.text("UPDATE meetings SET workspace_id = :workspace_id WHERE owner_id = :user_id"),
            {"workspace_id": workspace_id, "user_id": user_id},
        )


def downgrade():
    op.drop_index("ix_meetings_workspace_id", table_name="meetings")
    op.drop_column("meetings", "workspace_id")
    op.drop_index("ix_workspace_memberships_user_id", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_workspace_id", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
