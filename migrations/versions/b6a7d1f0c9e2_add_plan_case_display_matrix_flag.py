"""add plan_case display_matrix flag

Revision ID: b6a7d1f0c9e2
Revises: c3dbfd53af5a
Create Date: 2025-02-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6a7d1f0c9e2"
down_revision = "c3dbfd53af5a"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "is_display_matrix" not in {col["name"] for col in inspector.get_columns("plan_case")}:
        op.add_column(
            "plan_case",
            sa.Column(
                "is_display_matrix",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "is_display_matrix" in {col["name"] for col in inspector.get_columns("plan_case")}:
        op.drop_column("plan_case", "is_display_matrix")
