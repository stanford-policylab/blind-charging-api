# type: ignore
"""add gater table

Revision ID: fb649d51498d
Revises:
Create Date: 2024-12-17 23:39:02.478217

"""

from typing import Sequence, Union

import sqlalchemy as sa

import app
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb649d51498d"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "gater",
        sa.Column("id", app.server.db.UUID7Type(length=16), nullable=False),
        sa.Column("parent", app.server.db.UUID7Type(length=16), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "description",
            sa.String(length=4194303).with_variant(sa.NVARCHAR(length="max"), "mssql"),
            nullable=True,
        ),
        sa.Column(
            "blob",
            sa.String(length=4194303).with_variant(sa.NVARCHAR(length="max"), "mssql"),
            nullable=False,
        ),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent"],
            ["gater.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_gater_active"), "gater", ["active"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_gater_active"), table_name="gater")
    op.drop_table("gater")
    # ### end Alembic commands ###
