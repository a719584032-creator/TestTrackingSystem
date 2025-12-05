"""drop require_all_devices from plan_case

Revision ID: 7d2d3f3e4c1b
Revises: d24fa0b7d8c5
Create Date: 2025-02-19 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7d2d3f3e4c1b"
down_revision = "d24fa0b7d8c5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("plan_case") as batch_op:
        batch_op.drop_column("require_all_devices")


def downgrade():
    with op.batch_alter_table("plan_case") as batch_op:
        batch_op.add_column(
            sa.Column(
                "require_all_devices",
                sa.Boolean(),
                nullable=False,
                server_default="1",
                comment="是否需要在所有机型执行",
            )
        )
