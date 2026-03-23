"""Add custom_panels table to reference.db (P4-11).

User-uploaded gene panels for the rare variant finder. Stores
gene symbol lists and optional BED regions with metadata.

Revision ID: 004
Revises: 003
Create Date: 2026-03-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_panels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column(
            "gene_symbols",
            sa.Text,
            nullable=False,
            comment="JSON array of gene symbols",
        ),
        sa.Column(
            "bed_regions",
            sa.Text,
            comment="JSON array of {chrom, start, end, name} objects (BED source only)",
        ),
        sa.Column(
            "source_type",
            sa.Text,
            nullable=False,
            server_default="gene_list",
            comment="gene_list | bed",
        ),
        sa.Column("gene_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_custom_panels_name", "custom_panels", ["name"])


def downgrade() -> None:
    op.drop_index("idx_custom_panels_name", table_name="custom_panels")
    op.drop_table("custom_panels")
