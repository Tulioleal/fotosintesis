"""enrichment hardening: validation-to-evidence association and composite identity

Revision ID: 0011_enrichment_hardening
Revises: 0010_enrichment_persistence
Create Date: 2026-07-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_enrichment_hardening"
down_revision: Union[str, None] = "0010_enrichment_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enrichment_validation_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "validation_run_id",
            sa.Uuid(),
            sa.ForeignKey(
                "enrichment_validation_runs.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "validation_run_id",
            "document_id",
            name="uq_enrichment_validation_evidence_run_document",
        ),
    )
    op.create_index(
        "ix_enrichment_validation_evidence_document_run",
        "enrichment_validation_evidence",
        ["document_id", "validation_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_enrichment_validation_evidence_document_run",
        table_name="enrichment_validation_evidence",
    )
    op.drop_table("enrichment_validation_evidence")
