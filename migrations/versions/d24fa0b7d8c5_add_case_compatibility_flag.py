"""add case compatibility flag

Revision ID: d24fa0b7d8c5
Revises: 59c6bc626549
Create Date: 2025-02-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d24fa0b7d8c5"
down_revision = "59c6bc626549"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "test_case",
        sa.Column(
            "compatibility_testing",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "test_case_history",
        sa.Column(
            "compatibility_testing",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "plan_case",
        sa.Column(
            "snapshot_compatibility_testing",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade():
    op.drop_column("plan_case", "snapshot_compatibility_testing")
    op.drop_column("test_case_history", "compatibility_testing")
    op.drop_column("test_case", "compatibility_testing")
