from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.auth.tables import (
    application_jobs,
    candidate_enrichment_jobs,
    enrichment_job_progress,
    enrichment_validation_runs,
    knowledge_document_aspect_supports,
    knowledge_documents,
    taxonomy_provenance_snapshots,
)


def _constraint_names(table, constraint_type: type) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type) and constraint.name is not None
    }


def test_enrichment_tables_keep_identity_layers_separate() -> None:
    assert "uq_application_jobs_job_type_idempotency_key" in _constraint_names(
        application_jobs, UniqueConstraint
    )
    assert "uq_candidate_enrichment_jobs_candidate_policy" in _constraint_names(
        candidate_enrichment_jobs, UniqueConstraint
    )
    assert "uq_knowledge_document_aspect_supports_document_aspect" in _constraint_names(
        knowledge_document_aspect_supports, UniqueConstraint
    )
    assert "uq_taxonomy_provenance_species_source_version" in _constraint_names(
        taxonomy_provenance_snapshots, UniqueConstraint
    )
    assert "ck_enrichment_validation_runs_answerability_status" in _constraint_names(
        enrichment_validation_runs, CheckConstraint
    )

    content_identity = next(
        index
        for index in knowledge_documents.indexes
        if index.name == "uq_knowledge_documents_enrichment_content_identity"
    )
    assert [column.name for column in content_identity.columns] == [
        "canonical_species_key",
        "canonical_source_url",
        "source_version",
        "normalized_content_hash",
    ]
    assert "policy_version" not in knowledge_documents.c


def test_active_job_uniqueness_is_partial_and_terminal_reusable() -> None:
    active_index = next(
        index
        for index in application_jobs.indexes
        if index.name == "uq_application_jobs_active_deduplication_key"
    )
    ddl = str(CreateIndex(active_index).compile(dialect=postgresql.dialect()))

    assert "CREATE UNIQUE INDEX" in ddl
    assert "active_deduplication_key IS NOT NULL" in ddl
    assert "status IN ('pending', 'processing')" in ddl
    assert "complete" not in ddl
    assert "partial" not in ddl
    assert "failed" not in ddl


def test_enrichment_content_metadata_is_additive_for_legacy_rows() -> None:
    additive_columns = {
        "canonical_species_key",
        "accepted_gbif_key",
        "normalized_binomial",
        "canonical_source_url",
        "canonical_source_domain",
        "source_version",
        "normalized_content_hash",
        "source_retrieved_at",
        "source_published_at",
        "enrichment_provenance",
        "taxonomy_provenance_id",
    }

    assert additive_columns <= set(knowledge_documents.c.keys())
    assert all(knowledge_documents.c[name].nullable for name in additive_columns)


def test_enrichment_job_progress_table_is_bounded_and_job_referenced() -> None:
    expected_columns = {
        "job_id",
        "policy_version",
        "required_aspects",
        "local_covered_aspects",
        "persisted_covered_aspects",
        "indexed_covered_aspects",
        "final_judged_covered_aspects",
        "final_judged_missing_aspects",
        "answerability_status",
        "acquisition_avoided",
        "search_count",
        "accepted_aspect_count",
        "last_validation_run_id",
        "created_at",
        "updated_at",
    }
    assert expected_columns <= set(enrichment_job_progress.c.keys())
    assert set(enrichment_job_progress.c.keys()) <= expected_columns

    foreign_keys = list(enrichment_job_progress.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].column.table is application_jobs
    assert foreign_keys[0].column.name == "id"

    checks = _constraint_names(enrichment_job_progress, CheckConstraint)
    assert {
        "ck_enrichment_job_progress_policy_version",
        "ck_enrichment_job_progress_answerability_status",
        "ck_enrichment_job_progress_search_count",
        "ck_enrichment_job_progress_accepted_aspect_count",
    } <= checks

    assert enrichment_job_progress.c.search_count.nullable is False
    assert enrichment_job_progress.c.accepted_aspect_count.nullable is False
    assert enrichment_job_progress.c.acquisition_avoided.nullable is False
    assert enrichment_job_progress.c.final_judged_covered_aspects.nullable is True
    assert enrichment_job_progress.c.answerability_status.nullable is True
    assert enrichment_job_progress.c.last_validation_run_id.nullable is True
