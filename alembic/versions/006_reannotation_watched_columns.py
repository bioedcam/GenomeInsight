"""Add watched variant columns to reannotation_prompts (P4-21i).

Extends the re-annotation prompt to track watched variant
reclassifications separately. ``watched_count`` is the number of
watched variants that changed significance; ``watched_details`` is
a JSON array of {rsid, gene_symbol, old_significance, new_significance}.

Revision ID: 006
Revises: 005
Create Date: 2026-03-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reannotation_prompts",
        sa.Column("watched_count", sa.Integer, server_default="0"),
    )
    op.add_column(
        "reannotation_prompts",
        sa.Column(
            "watched_details",
            sa.Text,
            server_default="[]",
            comment="JSON array of watched variant reclassifications",
        ),
    )


def downgrade() -> None:
    op.drop_column("reannotation_prompts", "watched_details")
    op.drop_column("reannotation_prompts", "watched_count")
