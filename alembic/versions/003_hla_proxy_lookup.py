"""Add hla_proxy_lookup table to reference.db.

Static lookup table mapping HLA alleles to proxy tag SNPs with
linkage disequilibrium r² values and ancestry population context.
Populated from curated JSON at application startup.

Revision ID: 003
Revises: 002
Create Date: 2026-03-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── HLA Proxy Lookup ──────────────────────────────────────────
    op.create_table(
        "hla_proxy_lookup",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "hla_allele",
            sa.Text,
            nullable=False,
            comment="e.g. HLA-B*57:01",
        ),
        sa.Column(
            "proxy_rsid",
            sa.Text,
            nullable=False,
            comment="Tagging SNP rsid",
        ),
        sa.Column(
            "r_squared",
            sa.Float,
            nullable=False,
            comment="Linkage disequilibrium r² value",
        ),
        sa.Column(
            "ancestry_pop",
            sa.Text,
            nullable=False,
            comment="Ancestry population e.g. EUR, EAS, ALL",
        ),
        sa.Column(
            "clinical_context",
            sa.Text,
            comment="Clinical association e.g. Abacavir hypersensitivity",
        ),
        sa.Column(
            "pmid",
            sa.Text,
            comment="Supporting publication PMID",
        ),
    )
    op.create_index("idx_hla_proxy_rsid", "hla_proxy_lookup", ["proxy_rsid"])
    op.create_index("idx_hla_proxy_allele", "hla_proxy_lookup", ["hla_allele"])


def downgrade() -> None:
    op.drop_index("idx_hla_proxy_allele", table_name="hla_proxy_lookup")
    op.drop_index("idx_hla_proxy_rsid", table_name="hla_proxy_lookup")
    op.drop_table("hla_proxy_lookup")
