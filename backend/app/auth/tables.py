import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR


metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("name", sa.String(length=160), nullable=False),
    sa.Column("email", sa.String(length=320), nullable=False, unique=True, index=True),
    sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("password_hash", sa.Text(), nullable=True),
    sa.Column("image", sa.Text(), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("session_token", sa.String(length=255), nullable=False, unique=True, index=True),
    sa.Column("expires", sa.DateTime(timezone=True), nullable=False),
    sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
)

recovery_tokens = sa.Table(
    "recovery_tokens",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    sa.Column("token", sa.String(length=255), nullable=False, unique=True, index=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

identification_images = sa.Table(
    "identification_images",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("storage_path", sa.Text(), nullable=False),
    sa.Column("mime_type", sa.String(length=120), nullable=False),
    sa.Column("size_bytes", sa.Integer(), nullable=False),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("status", sa.String(length=40), nullable=False),
    sa.Column("sad_path", sa.String(length=80), nullable=True),
    sa.Column("message", sa.Text(), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

identification_candidates = sa.Table(
    "identification_candidates",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "identification_id",
        sa.Uuid(),
        sa.ForeignKey("identification_images.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("common_name", sa.String(length=180), nullable=True),
    sa.Column("suggested_scientific_name", sa.String(length=240), nullable=False),
    sa.Column("confidence_label", sa.String(length=40), nullable=False),
    sa.Column("visible_traits", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("possible_match_copy", sa.Text(), nullable=False),
    sa.Column("gbif_key", sa.Integer(), nullable=True),
    sa.Column("gbif_accepted_key", sa.Integer(), nullable=True),
    sa.Column("accepted_scientific_name", sa.String(length=240), nullable=True),
    sa.Column("binomial_name", sa.String(length=240), nullable=True),
    sa.Column("taxonomic_status", sa.String(length=80), nullable=True),
    sa.Column("synonyms", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("genus", sa.String(length=160), nullable=True),
    sa.Column("family", sa.String(length=160), nullable=True),
    sa.Column("species", sa.String(length=240), nullable=True),
    sa.Column("validation_status", sa.String(length=40), nullable=False),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

knowledge_documents = sa.Table(
    "knowledge_documents",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("species_id", sa.Uuid(), nullable=True, index=True),
    sa.Column("scientific_name", sa.String(length=240), nullable=False, index=True),
    sa.Column("topic", sa.String(length=120), nullable=False, index=True),
    sa.Column("title", sa.String(length=240), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.Column("review_status", sa.String(length=40), nullable=False, index=True),
    sa.Column("validated_claim_ingestion_key", sa.String(length=255), nullable=True),
    sa.Column("validated_claim_index_status", sa.String(length=20), nullable=True),
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
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint(
        "validated_claim_index_status IS NULL OR "
        "validated_claim_index_status IN ('pending', 'complete')",
        name="ck_knowledge_documents_validated_claim_index_status",
    ),
    sa.CheckConstraint(
        "canonical_species_key IS NULL OR ("
        "normalized_binomial IS NOT NULL AND canonical_source_url IS NOT NULL AND "
        "canonical_source_domain IS NOT NULL AND source_version IS NOT NULL AND "
        "normalized_content_hash IS NOT NULL AND source_retrieved_at IS NOT NULL AND "
        "enrichment_provenance IS NOT NULL AND taxonomy_provenance_id IS NOT NULL)",
        name="ck_knowledge_documents_enrichment_identity_complete",
    ),
)
sa.Index(
    "uq_knowledge_documents_validated_claim_ingestion_key",
    knowledge_documents.c.validated_claim_ingestion_key,
    unique=True,
    postgresql_where=knowledge_documents.c.validated_claim_ingestion_key.is_not(None),
    sqlite_where=knowledge_documents.c.validated_claim_ingestion_key.is_not(None),
)
sa.Index(
    "uq_knowledge_documents_enrichment_content_identity",
    knowledge_documents.c.canonical_species_key,
    knowledge_documents.c.canonical_source_url,
    knowledge_documents.c.source_version,
    knowledge_documents.c.normalized_content_hash,
    unique=True,
    postgresql_where=knowledge_documents.c.canonical_species_key.is_not(None),
    sqlite_where=knowledge_documents.c.canonical_species_key.is_not(None),
)

knowledge_sources = sa.Table(
    "knowledge_sources",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "document_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("title", sa.String(length=240), nullable=False),
    sa.Column("url", sa.Text(), nullable=False),
    sa.Column("source_domain", sa.String(length=180), nullable=False, index=True),
    sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("validation_status", sa.String(length=40), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

knowledge_chunks = sa.Table(
    "knowledge_chunks",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "document_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column(
        "source_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_sources.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("chunk_index", sa.Integer(), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("species_id", sa.Uuid(), nullable=True, index=True),
    sa.Column("scientific_name", sa.String(length=240), nullable=False, index=True),
    sa.Column("topic", sa.String(length=120), nullable=False, index=True),
    sa.Column("source_domain", sa.String(length=180), nullable=False, index=True),
    sa.Column("source_url", sa.Text(), nullable=False),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.Column("review_status", sa.String(length=40), nullable=False, index=True),
    sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

knowledge_embeddings = sa.Table(
    "knowledge_embeddings",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "chunk_id",
        sa.Uuid(),
        sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    ),
    sa.Column("provider", sa.String(length=120), nullable=False),
    sa.Column("model", sa.String(length=120), nullable=True),
    sa.Column("embedding", sa.JSON(), nullable=False),
    sa.Column("embedding_vector", VECTOR(8).with_variant(sa.JSON(), "sqlite"), nullable=True),
    sa.Column("embedding_dimension", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

plant_profiles = sa.Table(
    "plant_profiles",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "scientific_name", sa.String(length=240), nullable=False, unique=True, index=True
    ),
    sa.Column("common_name", sa.String(length=180), nullable=True),
    sa.Column("aliases", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("sections", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("confidence", sa.Float(), nullable=False),
    sa.Column("limitations", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

garden_plants = sa.Table(
    "garden_plants",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column(
        "profile_id",
        sa.Uuid(),
        sa.ForeignKey("plant_profiles.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "confirmed_candidate_id",
        sa.Uuid(),
        sa.ForeignKey("identification_candidates.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("nickname", sa.String(length=180), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("location", sa.String(length=180), nullable=True),
    sa.Column("image_path", sa.Text(), nullable=True),
    sa.Column("custom_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("active_reminders", sa.Integer(), nullable=False, server_default="0"),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    ),
)

conversations = sa.Table(
    "conversations",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("title", sa.String(length=240), nullable=True),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

conversation_messages = sa.Table(
    "conversation_messages",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column(
        "conversation_id",
        sa.Uuid(),
        sa.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("role", sa.String(length=40), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

reminders = sa.Table(
    "reminders",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column(
        "garden_plant_id",
        sa.Uuid(),
        sa.ForeignKey("garden_plants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("action", sa.String(length=120), nullable=False),
    sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recurrence", sa.String(length=80), nullable=True),
    sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
    sa.Column("suggestion_justification", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

application_jobs = sa.Table(
    "application_jobs",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
    sa.Column("conversation_id", sa.Uuid(), nullable=True),
    sa.Column("job_type", sa.String(length=80), nullable=False),
    sa.Column("payload_version", sa.Integer(), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
    sa.Column("idempotency_key", sa.String(length=255), nullable=False),
    sa.Column("active_deduplication_key", sa.String(length=255), nullable=True),
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
    sa.CheckConstraint("status IN ('pending', 'processing', 'complete', 'partial', 'failed')", name="ck_application_jobs_status"),
    sa.CheckConstraint(
        "job_type IN ('ingest_validated_claims', 'enrich_confirmed_plant')",
        name="ck_application_jobs_type",
    ),
    sa.CheckConstraint("payload_version >= 1", name="ck_application_jobs_payload_version"),
    sa.CheckConstraint("attempt_count >= 0", name="ck_application_jobs_attempt_count"),
    sa.CheckConstraint("max_attempts >= 1", name="ck_application_jobs_max_attempts"),
    sa.CheckConstraint(
        "(lease_owner IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
        "(lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL)",
        name="ck_application_jobs_lease_consistency",
    ),
)

sa.Index(
    "ix_application_jobs_status_available_at",
    application_jobs.c.status,
    application_jobs.c.available_at,
    postgresql_where=application_jobs.c.status.in_(["pending", "processing"]),
)
sa.Index(
    "uq_application_jobs_active_deduplication_key",
    application_jobs.c.active_deduplication_key,
    unique=True,
    postgresql_where=sa.and_(
        application_jobs.c.active_deduplication_key.is_not(None),
        application_jobs.c.status.in_(["pending", "processing"]),
    ),
    sqlite_where=sa.and_(
        application_jobs.c.active_deduplication_key.is_not(None),
        application_jobs.c.status.in_(["pending", "processing"]),
    ),
)

candidate_enrichment_jobs = sa.Table(
    "candidate_enrichment_jobs",
    metadata,
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
    sa.CheckConstraint("policy_version >= 1", name="ck_candidate_enrichment_jobs_policy_version"),
)
sa.Index(
    "ix_candidate_enrichment_jobs_owner_candidate_policy",
    candidate_enrichment_jobs.c.user_id,
    candidate_enrichment_jobs.c.candidate_id,
    candidate_enrichment_jobs.c.policy_version,
)
sa.Index("ix_candidate_enrichment_jobs_job_id", candidate_enrichment_jobs.c.job_id)

taxonomy_provenance_snapshots = sa.Table(
    "taxonomy_provenance_snapshots",
    metadata,
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
sa.Index(
    "ix_taxonomy_provenance_resolution",
    taxonomy_provenance_snapshots.c.accepted_gbif_key,
    taxonomy_provenance_snapshots.c.normalized_binomial,
    taxonomy_provenance_snapshots.c.resolved_at,
)

knowledge_document_aspect_supports = sa.Table(
    "knowledge_document_aspect_supports",
    metadata,
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
sa.Index(
    "ix_knowledge_document_aspect_supports_aspect",
    knowledge_document_aspect_supports.c.aspect,
)

enrichment_validation_runs = sa.Table(
    "enrichment_validation_runs",
    metadata,
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
    sa.CheckConstraint("policy_version >= 1", name="ck_enrichment_validation_runs_policy_version"),
    sa.CheckConstraint(
        "answerability_status IN ('full', 'partial', 'insufficient', 'contradictory')",
        name="ck_enrichment_validation_runs_answerability_status",
    ),
    sa.CheckConstraint(
        "judge_confidence >= 0 AND judge_confidence <= 1",
        name="ck_enrichment_validation_runs_judge_confidence",
    ),
)
sa.Index(
    "ix_enrichment_validation_runs_job_created_at",
    enrichment_validation_runs.c.job_id,
    enrichment_validation_runs.c.created_at,
)
sa.Index(
    "ix_enrichment_validation_runs_taxonomy_policy",
    enrichment_validation_runs.c.taxonomy_provenance_id,
    enrichment_validation_runs.c.policy_version,
)

enrichment_validation_evidence = sa.Table(
    "enrichment_validation_evidence",
    metadata,
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
sa.Index(
    "ix_enrichment_validation_evidence_document_run",
    enrichment_validation_evidence.c.document_id,
    enrichment_validation_evidence.c.validation_run_id,
)

sa.Index(
    "ix_application_jobs_processing_lease_expires",
    application_jobs.c.status,
    application_jobs.c.lease_expires_at,
    postgresql_where=application_jobs.c.status == "processing",
)

light_measurements = sa.Table(
    "light_measurements",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column(
        "garden_plant_id",
        sa.Uuid(),
        sa.ForeignKey("garden_plants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
    sa.Column("classification", sa.String(length=40), nullable=False),
    sa.Column("lux", sa.Float(), nullable=True),
    sa.Column("reliability", sa.String(length=40), nullable=False),
    sa.Column("source", sa.String(length=40), nullable=False, server_default="sensor"),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("measured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
