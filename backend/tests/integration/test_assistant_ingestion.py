import pytest

pytestmark = [
    pytest.mark.skipif(
        "SKIP_PG_TESTS" in __import__("os").environ,
        reason="PostgreSQL not available (SKIP_PG_TESTS is set)",
    ),
]


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setenv("JOBS_PRODUCER_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from app.core.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


_VALID_CLAIM_PAYLOAD = {
    "scientific_name": "Cotyledon tomentosa",
    "topic": "care",
    "source_url": "https://example.org/watering",
    "source_domain": "example.org",
    "source_provenance": "trusted",
    "claim": "Water weekly",
    "evidence_quote": "Water once a week in summer",
    "confidence": 0.95,
    "covered_aspects": ["watering"],
    "answerability_status": "full",
    "language": "en",
}


class TestAssistantDurableIngestion:
    @pytest.mark.parametrize(
        ("claim", "quote", "provenance"),
        [
            (
                "Prefiere luz brillante indirecta",
                "La especie crece mejor con luz filtrada",
                "trusted",
            ),
            (
                "Thrives in bright, indirect light",
                "Avoid prolonged direct afternoon sun",
                "trusted",
            ),
            (
                "Tolera luz tamizada",
                "La iluminación difusa favorece su desarrollo",
                "external_fallback",
            ),
        ],
    )
    async def test_final_judge_supported_multilingual_claim_enqueues(
        self, pg_session_factory, test_user, claim, quote, provenance, caplog
    ):
        """Real semantic-judge and web-answer nodes determine durable enqueue."""
        from types import SimpleNamespace
        import logging

        from app.assistant.graph.answers import _generate_web_answer
        from app.assistant.graph.plant_resolution import _sources_from_web_results
        from app.assistant.graph.web_evidence import _judge_combined_evidence
        from app.auth.tables import application_jobs
        from app.core.settings import get_settings
        from app.knowledge.page_evidence import TrustedPageEvidence
        from app.providers.types import SearchResult
        from sqlalchemy import select

        source_url = f"https://example.org/{provenance}/light"

        class FakeJudge:
            async def judge_response(self, payload, rubric):
                return SimpleNamespace(
                    status="full",
                    passed=True,
                    score=0.95,
                    confidence=0.95,
                    covered_aspects=["light_exposure"],
                    missing_aspects=[],
                    source_support=[
                        {
                            "claim": claim,
                            "source_urls": [source_url],
                            "covered_aspects": ["light_exposure"],
                            "evidence_quote": quote,
                            "confidence": 0.95,
                        }
                    ],
                    contradictions=[],
                    reasons=["direct source support"],
                )

        evidence = TrustedPageEvidence(
            result=SearchResult(
                title="Light guide",
                url=source_url,
                snippet=quote,
                source_domain="example.org",
            ),
            content=quote,
            validation_status=provenance,
            fetch_status="success",
            fetched_content_length=len(quote),
        )

        class FakeGraph:
            async def run(self, **kwargs):
                state = {
                    "message": "Cuidados de luz",
                    "topic": "light",
                    "plant_scientific_name": "Cotyledon tomentosa",
                    "display_plant_name": "Pata",
                    "required_aspects": ["light_exposure"],
                    "missing_aspects": ["light_exposure"],
                    "answer_language": "es" if "luz" in claim.casefold() else "en",
                    "sources": _sources_from_web_results([evidence]),
                }
                tools = SimpleNamespace(
                    providers=SimpleNamespace(judge=FakeJudge())
                )
                judged = await _judge_combined_evidence(
                    tools,
                    get_settings(),
                    state,
                    [evidence],
                )
                state.update(
                    {
                        "answerability_status": judged.status,
                        "answerability": judged.as_metadata(),
                        "source_support": judged.source_support,
                        "covered_aspects": judged.covered_aspects,
                        "missing_aspects": judged.missing_aspects,
                        "web_validation_confidence": judged.confidence,
                    }
                )

                class Owner:
                    async def _generate_grounded_answer(self, current_state, **_kwargs):
                        return {
                            "answer": "Respuesta validada.",
                            "sources": current_state["sources"],
                            "tool_failures": [],
                        }

                answer = await _generate_web_answer(Owner(), state, [evidence])
                return {**state, **answer}

        import types
        from app.assistant.schemas import AssistantChatRequest
        from app.assistant.service import AssistantService
        from app.assistant.tools import facade as tools_facade
        from unittest.mock import patch

        caplog.set_level(logging.INFO, logger="app.assistant.service")
        async with pg_session_factory() as session:
            service = AssistantService(session)
            service.graph = FakeGraph()
            with patch.object(
                tools_facade,
                "get_provider_registry",
                lambda: types.SimpleNamespace(embeddings=object()),
            ):
                await service.chat(
                    user_id=test_user,
                    payload=AssistantChatRequest(message="Cuidados", plant="Pata"),
                )
                await session.commit()
            jobs = (await session.execute(select(application_jobs))).all()

        assert len(jobs) == 1
        assert jobs[0]._mapping["job_type"] == "ingest_validated_claims"
        stored_claim = jobs[0]._mapping["payload"]["claims"][0]
        assert stored_claim["claim"] == claim
        assert stored_claim["evidence_quote"] == quote
        assert stored_claim["source_provenance"] == provenance
        assert stored_claim["answerability_status"] == "full"
        assert stored_claim["covered_aspects"] == ["light_exposure"]
        scheduled = next(
            record for record in caplog.records if record.message == "job_scheduled"
        )
        assert scheduled.__dict__["ctx_job_type"] == "ingest_validated_claims"
        assert scheduled.__dict__["ctx_payload_version"] == 1
        assert scheduled.__dict__["ctx_ownership_category"] == "user_owned"
        assert scheduled.__dict__["ctx_schedule_outcome"] == "created"
        assert scheduled.__dict__["ctx_job_id"] == str(jobs[0]._mapping["id"])
        service_logs = " ".join(str(record.__dict__) for record in caplog.records)
        assert claim not in service_logs
        assert quote not in service_logs
        assert source_url not in service_logs
        assert jobs[0]._mapping["idempotency_key"] not in service_logs

    async def test_response_persistence_and_enqueue_commit_together(
        self, pg_session_factory, test_user
    ):
        from app.auth.tables import application_jobs, conversation_messages
        from sqlalchemy import select

        class FakeGraph:
            async def run(self, **kwargs):
                return {
                    "answer": "Water weekly.",
                    "sources": [],
                    "tool_failures": [],
                    "ingestion_claims": [_VALID_CLAIM_PAYLOAD],
                    "answerability_status": "full",
                }

        import types
        from app.assistant.service import AssistantService
        from app.assistant.schemas import AssistantChatRequest
        from app.assistant.tools import facade as tools_facade
        from unittest.mock import patch

        async with pg_session_factory() as s:
            service = AssistantService(s)
            service.graph = FakeGraph()
            with patch.object(tools_facade, "get_provider_registry", lambda: types.SimpleNamespace(embeddings=object())):
                await service.chat(
                    user_id=test_user,
                    payload=AssistantChatRequest(message="How do I water?", plant="Pata"),
                )
                await s.commit()

                msg_count = (await s.execute(select(conversation_messages))).all()
                job_count = (await s.execute(select(application_jobs))).all()

        assert len(msg_count) >= 1
        assert len(job_count) >= 1

    async def test_rollback_persists_neither_response_nor_job(
        self, pg_session_factory, test_user
    ):
        from app.auth.tables import application_jobs, conversation_messages
        from sqlalchemy import select

        class FakeGraph:
            async def run(self, **kwargs):
                return {
                    "answer": "Rollback test.",
                    "sources": [],
                    "tool_failures": [],
                    "ingestion_claims": [_VALID_CLAIM_PAYLOAD],
                    "answerability_status": "full",
                }

        import types
        from app.assistant.service import AssistantService
        from app.assistant.schemas import AssistantChatRequest
        from app.assistant.tools import facade as tools_facade
        from unittest.mock import patch
        from uuid import uuid4

        from app.jobs.repository import JobRepository

        async def failing_enqueue(*_args, **_kwargs):
            raise RuntimeError("forced enqueue failure")

        async with pg_session_factory() as s:
            service = AssistantService(s)
            service.graph = FakeGraph()
            with patch.object(
                tools_facade,
                "get_provider_registry",
                lambda: types.SimpleNamespace(embeddings=object()),
            ):
                with patch.object(JobRepository, "enqueue_result", new=failing_enqueue):
                    with pytest.raises(RuntimeError):
                        await service.chat(
                            user_id=test_user,
                            payload=AssistantChatRequest(
                                message="Rollback me", plant="Pata"
                            ),
                        )

        async with pg_session_factory() as verification:
            msg_count = (
                await verification.execute(select(conversation_messages))
            ).all()
            job_count = (
                await verification.execute(select(application_jobs))
            ).all()

        assert len(msg_count) == 0
        assert len(job_count) == 0

    async def test_empty_claims_enqueue_nothing(self, pg_session_factory, test_user):
        from app.auth.tables import application_jobs
        from sqlalchemy import select

        class FakeGraphEmpty:
            async def run(self, **kwargs):
                return {
                    "answer": "No claims.",
                    "sources": [],
                    "tool_failures": [],
                    "ingestion_claims": [],
                }

        import types
        from app.assistant.service import AssistantService
        from app.assistant.schemas import AssistantChatRequest
        from app.assistant.tools import facade as tools_facade
        from unittest.mock import patch

        async with pg_session_factory() as s:
            service = AssistantService(s)
            service.graph = FakeGraphEmpty()
            with patch.object(tools_facade, "get_provider_registry", lambda: types.SimpleNamespace(embeddings=object())):
                await service.chat(
                    user_id=test_user,
                    payload=AssistantChatRequest(message="Empty claims", plant="Pata"),
                )
                await s.commit()

                rows = (await s.execute(select(application_jobs))).all()
        assert len(rows) == 0

    async def test_worker_absence_does_not_remove_response(
        self, pg_session_factory, test_user
    ):
        from app.auth.tables import (
            application_jobs,
            conversation_messages,
            knowledge_chunks,
            knowledge_documents,
            knowledge_embeddings,
            knowledge_sources,
        )
        from sqlalchemy import func, select

        class FakeGraph:
            async def run(self, **kwargs):
                return {
                    "answer": "Worker can be absent.",
                    "sources": [],
                    "tool_failures": [],
                    "ingestion_claims": [_VALID_CLAIM_PAYLOAD],
                    "answerability_status": "full",
                }

        import types
        from app.assistant.service import AssistantService
        from app.assistant.schemas import AssistantChatRequest
        from app.assistant.tools import facade as tools_facade
        from unittest.mock import patch

        async with pg_session_factory() as s:
            service = AssistantService(s)
            service.graph = FakeGraph()
            with patch.object(tools_facade, "get_provider_registry", lambda: types.SimpleNamespace(embeddings=object())):
                response = await service.chat(
                    user_id=test_user,
                    payload=AssistantChatRequest(message="Worker absent?", plant="Pata"),
                )
                await s.commit()

        async with pg_session_factory() as verification:
            messages = (
                await verification.execute(
                    select(conversation_messages).where(
                        conversation_messages.c.conversation_id
                        == response.conversation_id
                    )
                )
            ).all()
            jobs = (
                await verification.execute(
                    select(application_jobs).where(
                        application_jobs.c.conversation_id
                        == response.conversation_id
                    )
                )
            ).all()
            knowledge_counts = [
                int(await verification.scalar(select(func.count()).select_from(table)) or 0)
                for table in (
                    knowledge_documents,
                    knowledge_sources,
                    knowledge_chunks,
                    knowledge_embeddings,
                )
            ]

        assert response.message.content == "Worker can be absent."
        assert len(messages) >= 1
        assert len(jobs) == 1
        assert jobs[0]._mapping["status"] == "pending"
        assert jobs[0]._mapping["user_id"] == test_user
        assert jobs[0]._mapping["conversation_id"] == response.conversation_id
        assert knowledge_counts == [0, 0, 0, 0]

    async def test_exhausted_ingestion_does_not_remove_response(
        self, pg_session_factory, test_user, monkeypatch, caplog
    ):
        import asyncio
        import logging

        from app.assistant.schemas import AssistantChatRequest
        from app.assistant.service import AssistantService
        from app.auth.tables import application_jobs, conversation_messages
        from app.core.settings import get_settings
        from app.jobs.handler import HandlerRegistry, JobHandler, JobHandlerResult
        from app.jobs.schemas import (
            IngestValidatedClaimsPayload,
            JobFailureCategory,
            JobStatus,
            JobType,
        )
        from app.jobs.worker import Worker
        from sqlalchemy import select, update

        class FakeGraph:
            async def run(self, **kwargs):
                claim = {**_VALID_CLAIM_PAYLOAD, "claim": "SENSITIVE_EXHAUSTED_CLAIM"}
                return {
                    "answer": "Persisted before worker failure.",
                    "sources": [],
                    "tool_failures": [],
                    "ingestion_claims": [claim],
                    "answerability_status": "full",
                }

        class _FailingHandler(JobHandler):
            def supported_payload_versions(self) -> list[int]:
                return [1]

            def payload_model(self, payload_version: int):
                return IngestValidatedClaimsPayload

            async def handle(self, *, payload, attempt_count, max_attempts):
                return JobHandlerResult.failed(
                    category=JobFailureCategory.provider_transient,
                    retryable=True,
                )

        async with pg_session_factory() as session:
            service = AssistantService(session)
            service.graph = FakeGraph()
            response = await service.chat(
                user_id=test_user,
                payload=AssistantChatRequest(message="Persist then fail", plant="Pata"),
            )
            await session.commit()
            job_id = await session.scalar(
                select(application_jobs.c.id).where(
                    application_jobs.c.conversation_id == response.conversation_id
                )
            )
            await session.execute(
                update(application_jobs)
                .where(application_jobs.c.id == job_id)
                .values(max_attempts=1)
            )
            await session.commit()

        monkeypatch.setenv("JOBS_WORKER_ENABLED", "true")
        monkeypatch.setenv("JOBS_METRICS_PORT", "0")
        get_settings.cache_clear()
        registry = HandlerRegistry()
        registry.register(
            JobType.ingest_validated_claims.value,
            _FailingHandler(),
            payload_model=IngestValidatedClaimsPayload,
        )
        worker = Worker(
            session_factory=pg_session_factory,
            handler_registry=registry,
            settings=get_settings(),
        )
        caplog.set_level(logging.INFO, logger="app.jobs.worker")
        task = asyncio.create_task(worker.start())
        for _ in range(80):
            async with pg_session_factory() as verification:
                job = (
                    await verification.execute(
                        select(
                            application_jobs.c.status,
                            application_jobs.c.last_error,
                        ).where(application_jobs.c.id == job_id)
                    )
                ).mappings().one()
            if job["status"] == JobStatus.failed.value:
                break
            await asyncio.sleep(0.05)
        worker.stop()
        await task

        async with pg_session_factory() as verification:
            message = await verification.scalar(
                select(conversation_messages.c.content).where(
                    conversation_messages.c.conversation_id == response.conversation_id,
                    conversation_messages.c.role == "assistant",
                )
            )
        assert job["status"] == JobStatus.failed.value
        assert job["last_error"] == {
            "category": "provider_transient",
            "retryable": False,
        }
        assert message == "Persisted before worker failure."
        assert "SENSITIVE_EXHAUSTED_CLAIM" not in " ".join(
            str(record.__dict__) for record in caplog.records
        )

    async def test_retry_does_not_duplicate_documents(
        self, pg_session_factory
    ):
        from datetime import datetime, timezone
        from app.jobs.handlers.ingest_validated_claims import (
            compute_claim_ingestion_key,
        )
        from app.knowledge.repository import KnowledgeRepository
        from app.knowledge.schemas import KnowledgeDocumentInput, KnowledgeSourceInput
        from app.knowledge.chunking import chunk_document

        claim = {
            "scientific_name": "Test plant",
            "topic": "care",
            "source_url": "https://example.org/retry-idempotent",
            "source_domain": "example.org",
            "source_provenance": "trusted",
            "claim": "Idempotent retry test",
            "evidence_quote": "Test evidence",
            "confidence": 0.9,
            "covered_aspects": ["watering"],
            "answerability_status": "full",
            "language": "en",
        }

        ingestion_key = compute_claim_ingestion_key(claim)

        async with pg_session_factory() as s:
            repo = KnowledgeRepository(s)
            existing = await repo.find_document_by_ingestion_key(ingestion_key)
            assert existing is None

            doc = KnowledgeDocumentInput(
                species_id=None,
                scientific_name=claim["scientific_name"],
                topic=claim["topic"],
                title="Test",
                content=claim["claim"],
                confidence=claim["confidence"],
                review_status="auto_ingested",
                sources=[
                    KnowledgeSourceInput(
                        title="Test source",
                        url=claim["source_url"],
                        source_domain=claim["source_domain"],
                        retrieved_at=datetime.now(timezone.utc),
                        validation_status="trusted",
                    ),
                ],
            )
            doc.metadata["claim_ingestion_key"] = ingestion_key
            chunks = chunk_document(doc)

            persisted = await repo.save_document(
                doc, chunks=chunks, ingestion_key=ingestion_key,
            )
            await s.commit()

            existing_id = await repo.find_document_by_ingestion_key(ingestion_key)
            assert existing_id == persisted.id

        async with pg_session_factory() as s:
            repo = KnowledgeRepository(s)
            same_id = await repo.find_document_by_ingestion_key(ingestion_key)
            assert same_id == persisted.id
