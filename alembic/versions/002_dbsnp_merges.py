"""Add dbsnp_merges table and dbSNP columns to annotated_variants.

Revision ID: 002
Revises: 001
Create Date: 2026-03-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── dbSNP Merged rsids ────────────────────────────────────────
    op.create_table(
        "dbsnp_merges",
        sa.Column("old_rsid", sa.Text, primary_key=True),
        sa.Column("current_rsid", sa.Text, nullable=False),
        sa.Column(
            "build_id",
            sa.Integer,
            comment="dbSNP build where merge occurred",
        ),
    )
    op.create_index("idx_dbsnp_merges_current", "dbsnp_merges", ["current_rsid"])


def downgrade() -> None:
    op.drop_table("dbsnp_merges")
