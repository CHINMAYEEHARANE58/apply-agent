"""Bind local UUID accounts to verified Clerk identities.

Revision ID: 20261010_0006
Revises: 20261010_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_0006"
down_revision = "20261010_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("clerk_user_id", sa.String(255), nullable=True))
    op.create_index("ix_users_clerk_user_id", "users", ["clerk_user_id"], unique=True)
    # Phase 5 models introduced timestamps but omitted migration columns.
    for table in ("candidate_profiles", "internship_preferences"):
        with op.batch_alter_table(table) as batch:
            for name in ("created_at", "updated_at"):
                batch.add_column(sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    for table in ("candidate_profiles", "internship_preferences"):
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_column("users", "clerk_user_id")
