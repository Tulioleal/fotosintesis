"""durable background jobs

Revision ID: 0009_durable_background_jobs
Revises: 0008_candidate_binomial_name
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_durable_background_jobs"
down_revision: Union[str, None] = "0008_candidate_binomial_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_token", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_type", "idempotency_key", name="uq_application_jobs_job_type_idempotency_key"),
    )
    op.create_index("ix_application_jobs_user_id", "application_jobs", ["user_id"])
    op.create_index(
        "ix_application_jobs_status_available_at",
        "application_jobs",
        ["status", "available_at"],
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )
    op.create_index(
        "ix_application_jobs_processing_lease_expires",
        "application_jobs",
        ["status", "lease_expires_at"],
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.execute(
        "ALTER TABLE application_jobs "
        "ADD CONSTRAINT ck_application_jobs_status CHECK (status IN ('pending', 'processing', 'complete', 'partial', 'failed'))"
    )
    op.execute(
        "ALTER TABLE application_jobs "
        "ADD CONSTRAINT ck_application_jobs_type CHECK (job_type IN ('ingest_validated_claims'))"
    )
    op.execute(
        "ALTER TABLE application_jobs "
        "ADD CONSTRAINT ck_application_jobs_payload_version CHECK (payload_version >= 1)"
    )
    op.execute(
        "ALTER TABLE application_jobs "
        "ADD CONSTRAINT ck_application_jobs_attempt_count CHECK (attempt_count >= 0)"
    )
    op.execute(
        "ALTER TABLE application_jobs "
        "ADD CONSTRAINT ck_application_jobs_max_attempts CHECK (max_attempts >= 1)"
    )
    op.execute(
        "ALTER TABLE application_jobs "
        "ADD CONSTRAINT ck_application_jobs_lease_consistency CHECK ("
        "(lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
        "(lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)"
        ")"
    )

    op.add_column(
        "knowledge_documents",
        sa.Column("validated_claim_ingestion_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("validated_claim_index_status", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "ck_knowledge_documents_validated_claim_index_status",
        "knowledge_documents",
        "validated_claim_index_status IS NULL OR "
        "validated_claim_index_status IN ('pending', 'complete')",
    )
    op.create_index(
        "uq_knowledge_documents_validated_claim_ingestion_key",
        "knowledge_documents",
        ["validated_claim_ingestion_key"],
        unique=True,
        postgresql_where=sa.text("validated_claim_ingestion_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_knowledge_documents_validated_claim_ingestion_key", table_name="knowledge_documents")
    op.drop_constraint(
        "ck_knowledge_documents_validated_claim_index_status",
        "knowledge_documents",
        type_="check",
    )
    op.drop_column("knowledge_documents", "validated_claim_index_status")
    op.drop_column("knowledge_documents", "validated_claim_ingestion_key")
    op.execute("ALTER TABLE application_jobs DROP CONSTRAINT IF EXISTS ck_application_jobs_lease_consistency")
    op.execute("ALTER TABLE application_jobs DROP CONSTRAINT IF EXISTS ck_application_jobs_max_attempts")
    op.execute("ALTER TABLE application_jobs DROP CONSTRAINT IF EXISTS ck_application_jobs_attempt_count")
    op.execute("ALTER TABLE application_jobs DROP CONSTRAINT IF EXISTS ck_application_jobs_payload_version")
    op.execute("ALTER TABLE application_jobs DROP CONSTRAINT IF EXISTS ck_application_jobs_type")
    op.execute("ALTER TABLE application_jobs DROP CONSTRAINT IF EXISTS ck_application_jobs_status")
    op.drop_index("ix_application_jobs_processing_lease_expires", table_name="application_jobs")
    op.drop_index("ix_application_jobs_status_available_at", table_name="application_jobs")
    op.drop_index("ix_application_jobs_user_id", table_name="application_jobs")
    op.drop_constraint("uq_application_jobs_job_type_idempotency_key", "application_jobs", type_="unique")
    op.drop_table("application_jobs")
