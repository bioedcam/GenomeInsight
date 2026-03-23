"""Add overlay_configs table to reference.db (P4-12).

User-uploaded BED/VCF annotation overlays. Stores overlay metadata
and column names. Per-variant overlay results live in sample DBs.

Revision ID: 005
Revises: 004
Create Date: 2026-03-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "overlay_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column(
            "file_type",
            sa.Text,
            nullable=False,
            comment="bed | vcf",
        ),
        sa.Column(
            "column_names",
            sa.Text,
            nullable=False,
            comment="JSON array of annotation column names from the overlay file",
        ),
        sa.Column("region_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_overlay_configs_name", "overlay_configs", ["name"])


def downgrade() -> None:
    op.drop_index("idx_overlay_configs_name", table_name="overlay_configs")
    op.drop_table("overlay_configs")
