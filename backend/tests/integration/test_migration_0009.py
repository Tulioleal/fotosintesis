from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from .conftest import BASE_DATABASE_URL


BACKEND_ROOT = Path(__file__).resolve().parents[2]


async def _run_alembic(database_url: str, revision: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url}
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def test_upgrade_0008_to_0009_preserves_knowledge_and_adds_job_contract() -> None:
    database_name = f"migration_{uuid4().hex}"
    admin_engine = create_async_engine(
        BASE_DATABASE_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=False,
    )
    database_url = make_url(BASE_DATABASE_URL).set(database=database_name).render_as_string(
        hide_password=False
    )
    database_engine = None

    try:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        await _run_alembic(database_url, "0008_candidate_binomial_name")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        document_id = uuid4()
        async with database_engine.begin() as connection:
            await connection.execute(
                text("""
                    INSERT INTO knowledge_documents (
                        id, scientific_name, topic, title, content,
                        confidence, review_status
                    ) VALUES (
                        CAST(:id AS uuid), 'Monstera deliciosa', 'watering',
                        'Existing guidance', 'Preserve this content', 0.9, 'approved'
                    )
                """),
                {"id": str(document_id)},
            )
        await database_engine.dispose()
        database_engine = None

        await _run_alembic(database_url, "0009_durable_background_jobs")
        database_engine = create_async_engine(database_url, pool_pre_ping=False)
        second_document_id = uuid4()
        distinct_document_id = uuid4()
        async with database_engine.begin() as connection:
            await connection.execute(
                text("""
                    INSERT INTO knowledge_documents (
                        id, scientific_name, topic, title, content,
                        confidence, review_status
                    ) VALUES (
                        CAST(:id AS uuid), 'Rosa canina', 'pruning',
                        'Second legacy row', 'Second preserved content', 0.8, 'approved'
                    )
                """),
                {"id": str(second_document_id)},
            )
            null_keys = await connection.scalar(
                text("""
                    SELECT count(*) FROM knowledge_documents
                    WHERE validated_claim_ingestion_key IS NULL
                """)
            )
            assert null_keys == 2
            await connection.execute(
                text("""
                    UPDATE knowledge_documents
                    SET validated_claim_ingestion_key = 'stable-key-one'
                    WHERE id = CAST(:id AS uuid)
                """),
                {"id": str(document_id)},
            )
            await connection.execute(
                text("""
                    INSERT INTO knowledge_documents (
                        id, scientific_name, topic, title, content,
                        confidence, review_status, validated_claim_ingestion_key,
                        validated_claim_index_status
                    ) VALUES (
                        CAST(:id AS uuid), 'Ficus elastica', 'light',
                        'Distinct key row', 'Distinct content', 0.9, 'approved',
                        'stable-key-two', 'pending'
                    )
                """),
                {"id": str(distinct_document_id)},
            )
        with pytest.raises(IntegrityError):
            async with database_engine.begin() as connection:
                await connection.execute(
                    text("""
                        INSERT INTO knowledge_documents (
                            id, scientific_name, topic, title, content,
                            confidence, review_status,
                            validated_claim_ingestion_key,
                            validated_claim_index_status
                        ) VALUES (
                            CAST(:id AS uuid), 'Duplicate key', 'care',
                            'Duplicate', 'Must be rejected', 0.9, 'approved',
                            'stable-key-one', 'pending'
                        )
                    """),
                    {"id": str(uuid4())},
                )
        async with database_engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            document = (
                await connection.execute(
                    text("""
                        SELECT content, validated_claim_ingestion_key,
                               validated_claim_index_status
                        FROM knowledge_documents
                        WHERE id = CAST(:id AS uuid)
                    """),
                    {"id": str(document_id)},
                )
            ).mappings().one()
            index_rows = (
                await connection.execute(
                    text("""
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = current_schema()
                          AND tablename IN ('application_jobs', 'knowledge_documents')
                    """)
                )
            )
            indexes = {row.indexname: row.indexdef for row in index_rows}
            constraints = set(
                (
                    await connection.execute(
                        text("""
                            SELECT constraint_name
                            FROM information_schema.table_constraints
                            WHERE table_schema = current_schema()
                              AND table_name IN ('application_jobs', 'knowledge_documents')
                        """)
                    )
                ).scalars()
            )

        assert revision == "0009_durable_background_jobs"
        assert document == {
            "content": "Preserve this content",
            "validated_claim_ingestion_key": "stable-key-one",
            "validated_claim_index_status": None,
        }
        assert {
            "ix_application_jobs_status_available_at",
            "ix_application_jobs_processing_lease_expires",
            "uq_knowledge_documents_validated_claim_ingestion_key",
        } <= indexes.keys()
        assert {
            "ck_application_jobs_status",
            "ck_application_jobs_type",
            "ck_application_jobs_payload_version",
            "ck_application_jobs_attempt_count",
            "ck_application_jobs_max_attempts",
            "ck_application_jobs_lease_consistency",
            "uq_application_jobs_job_type_idempotency_key",
            "ck_knowledge_documents_validated_claim_index_status",
        } <= constraints
        ingestion_index = indexes[
            "uq_knowledge_documents_validated_claim_ingestion_key"
        ]
        assert "UNIQUE INDEX" in ingestion_index
        assert "validated_claim_ingestion_key IS NOT NULL" in ingestion_index
    finally:
        if database_engine is not None:
            await database_engine.dispose()
        try:
            async with admin_engine.connect() as connection:
                await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        finally:
            await admin_engine.dispose()
