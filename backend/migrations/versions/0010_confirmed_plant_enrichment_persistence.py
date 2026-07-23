"""confirmed plant enrichment persistence

Revision ID: 0010_enrichment_persistence
Revises: 0009_durable_background_jobs
Create Date: 2026-07-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_enrichment_persistence"
down_revision: Union[str, None] = "0009_durable_background_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "application_jobs",
        sa.Column("active_deduplication_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "uq_application_jobs_active_deduplication_key",
        "application_jobs",
        ["active_deduplication_key"],
        unique=True,
        postgresql_where=sa.text(
            "active_deduplication_key IS NOT NULL "
            "AND status IN ('pending', 'processing')"
        ),
    )
    op.drop_constraint("ck_application_jobs_type", "application_jobs", type_="check")
    op.create_check_constraint(
        "ck_application_jobs_type",
        "application_jobs",
        "job_type IN ('ingest_validated_claims', 'enrich_confirmed_plant')",
    )

    op.create_table(
        "candidate_enrichment_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("identification_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("application_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "candidate_id",
            "policy_version",
            name="uq_candidate_enrichment_jobs_candidate_policy",
        ),
        sa.CheckConstraint(
            "policy_version >= 1",
            name="ck_candidate_enrichment_jobs_policy_version",
        ),
    )
    op.create_index(
        "ix_candidate_enrichment_jobs_owner_candidate_policy",
        "candidate_enrichment_jobs",
        ["user_id", "candidate_id", "policy_version"],
    )
    op.create_index(
        "ix_candidate_enrichment_jobs_job_id", "candidate_enrichment_jobs", ["job_id"]
    )

    op.create_table(
        "taxonomy_provenance_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("canonical_species_key", sa.String(length=512), nullable=False),
        sa.Column("accepted_gbif_key", sa.Integer(), nullable=True),
        sa.Column("normalized_binomial", sa.String(length=240), nullable=False),
        sa.Column("taxonomy_source", sa.String(length=80), nullable=False, server_default="gbif"),
        sa.Column("taxonomy_source_version", sa.String(length=255), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "previous_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("taxonomy_provenance_snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "canonical_species_key",
            "taxonomy_source",
            "taxonomy_source_version",
            name="uq_taxonomy_provenance_species_source_version",
        ),
    )
    op.create_index(
        "ix_taxonomy_provenance_resolution",
        "taxonomy_provenance_snapshots",
        ["accepted_gbif_key", "normalized_binomial", "resolved_at"],
    )

    for column in (
        sa.Column("canonical_species_key", sa.String(length=512), nullable=True),
        sa.Column("accepted_gbif_key", sa.Integer(), nullable=True),
        sa.Column("normalized_binomial", sa.String(length=240), nullable=True),
        sa.Column("canonical_source_url", sa.Text(), nullable=True),
        sa.Column("canonical_source_domain", sa.String(length=180), nullable=True),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("normalized_content_hash", sa.String(length=64), nullable=True),
        sa.Column("source_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrichment_provenance", sa.JSON(), nullable=True),
        sa.Column(
            "taxonomy_provenance_id",
            sa.Uuid(),
            sa.ForeignKey("taxonomy_provenance_snapshots.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    ):
        op.add_column("knowledge_documents", column)
    op.create_check_constraint(
        "ck_knowledge_documents_enrichment_identity_complete",
        "knowledge_documents",
        "canonical_species_key IS NULL OR ("
        "normalized_binomial IS NOT NULL AND canonical_source_url IS NOT NULL AND "
        "canonical_source_domain IS NOT NULL AND source_version IS NOT NULL AND "
        "normalized_content_hash IS NOT NULL AND source_retrieved_at IS NOT NULL AND "
        "enrichment_provenance IS NOT NULL AND taxonomy_provenance_id IS NOT NULL)",
    )
    op.create_index(
        "uq_knowledge_documents_enrichment_content_identity",
        "knowledge_documents",
        [
            "canonical_species_key",
            "canonical_source_url",
            "source_version",
            "normalized_content_hash",
        ],
        unique=True,
        postgresql_where=sa.text("canonical_species_key IS NOT NULL"),
    )

    op.create_table(
        "knowledge_document_aspect_supports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("aspect", sa.String(length=120), nullable=False),
        sa.Column("support_confidence", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "document_id",
            "aspect",
            name="uq_knowledge_document_aspect_supports_document_aspect",
        ),
        sa.CheckConstraint(
            "support_confidence >= 0 AND support_confidence <= 1",
            name="ck_knowledge_document_aspect_supports_confidence",
        ),
    )
    op.create_index(
        "ix_knowledge_document_aspect_supports_aspect",
        "knowledge_document_aspect_supports",
        ["aspect"],
    )

    op.create_table(
        "enrichment_validation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Uuid(),
            sa.ForeignKey("application_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "taxonomy_provenance_id",
            sa.Uuid(),
            sa.ForeignKey("taxonomy_provenance_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("required_aspects", sa.JSON(), nullable=False),
        sa.Column("covered_aspects", sa.JSON(), nullable=False),
        sa.Column("missing_aspects", sa.JSON(), nullable=False),
        sa.Column("answerability_status", sa.String(length=20), nullable=False),
        sa.Column("judge_confidence", sa.Float(), nullable=False),
        sa.Column("validation_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "policy_version >= 1",
            name="ck_enrichment_validation_runs_policy_version",
        ),
        sa.CheckConstraint(
            "answerability_status IN ('full', 'partial', 'insufficient', 'contradictory')",
            name="ck_enrichment_validation_runs_answerability_status",
        ),
        sa.CheckConstraint(
            "judge_confidence >= 0 AND judge_confidence <= 1",
            name="ck_enrichment_validation_runs_judge_confidence",
        ),
    )
    op.create_index(
        "ix_enrichment_validation_runs_job_created_at",
        "enrichment_validation_runs",
        ["job_id", "created_at"],
    )
    op.create_index(
        "ix_enrichment_validation_runs_taxonomy_policy",
        "enrichment_validation_runs",
        ["taxonomy_provenance_id", "policy_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_enrichment_validation_runs_taxonomy_policy",
        table_name="enrichment_validation_runs",
    )
    op.drop_index(
        "ix_enrichment_validation_runs_job_created_at",
        table_name="enrichment_validation_runs",
    )
    op.drop_table("enrichment_validation_runs")
    op.drop_index(
        "ix_knowledge_document_aspect_supports_aspect",
        table_name="knowledge_document_aspect_supports",
    )
    op.drop_table("knowledge_document_aspect_supports")
    op.drop_index(
        "uq_knowledge_documents_enrichment_content_identity",
        table_name="knowledge_documents",
    )
    op.drop_constraint(
        "ck_knowledge_documents_enrichment_identity_complete",
        "knowledge_documents",
        type_="check",
    )
    for column_name in (
        "taxonomy_provenance_id",
        "enrichment_provenance",
        "source_published_at",
        "source_retrieved_at",
        "normalized_content_hash",
        "source_version",
        "canonical_source_domain",
        "canonical_source_url",
        "normalized_binomial",
        "accepted_gbif_key",
        "canonical_species_key",
    ):
        op.drop_column("knowledge_documents", column_name)
    op.drop_index(
        "ix_taxonomy_provenance_resolution",
        table_name="taxonomy_provenance_snapshots",
    )
    op.drop_table("taxonomy_provenance_snapshots")
    op.drop_index("ix_candidate_enrichment_jobs_job_id", table_name="candidate_enrichment_jobs")
    op.drop_index(
        "ix_candidate_enrichment_jobs_owner_candidate_policy",
        table_name="candidate_enrichment_jobs",
    )
    op.drop_table("candidate_enrichment_jobs")
    op.drop_constraint("ck_application_jobs_type", "application_jobs", type_="check")
    op.create_check_constraint(
        "ck_application_jobs_type",
        "application_jobs",
        "job_type IN ('ingest_validated_claims')",
    )
    op.drop_index(
        "uq_application_jobs_active_deduplication_key",
        table_name="application_jobs",
    )
    op.drop_column("application_jobs", "active_deduplication_key")
