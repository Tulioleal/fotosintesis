"""Evaluation runner that executes the actual assistant graph.

The runner builds an isolated in-memory session, constructs the real
``AssistantTools``/``AssistantGraph`` backed by a recording or deterministic
provider registry, runs every case through the graph, and projects the
observed result from the returned ``AssistantState``. Observed output is never
derived from reference fixtures.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.assistant.graph import AssistantGraph
from app.assistant.repository import AssistantRepository
from app.assistant.tools import AssistantTools
from app.auth.tables import metadata
from app.evaluation.dataset import EvaluationCase, load_seed_cases
from app.evaluation.metrics import (
    DEFAULT_EVALUATION_PROFILE,
    EvaluationMetricError,
    EvaluationProfile,
    aggregate_pass_rate_met,
    apply_per_case_thresholds,
    bertscore,
    precision_at_k,
    retrieval_recall_at_k,
    rouge_l,
    tool_assertion_metrics,
    tool_success_rate,
)
from app.evaluation.reconcile import reconcile_cases
from app.evaluation.recordings import (
    RecordingMode,
    RecordingStore,
    RecordingError,
)
from app.evaluation.registry import RecordingProviderRegistry
from app.evaluation.report import render_markdown_report
from app.knowledge.rag import KnowledgeVectorIndex
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeDocumentInput,
    KnowledgeSourceInput,
    ReviewStatus,
)
from app.providers.factory import ProviderRegistry, get_provider_registry
from app.providers.interfaces import JudgeEvaluationProvider
from app.providers.types import JudgeResult

JUDGE_RUBRIC = {
    "criteria": {
        "grounding": "Answer is supported by retrieved evidence or provided case context.",
        "botanical_correctness": "Botanical advice is plausible and avoids harmful care claims.",
        "usefulness": "Answer gives actionable next steps for the user's plant-care goal.",
        "clarity": "Answer is concise, understandable and avoids unsupported certainty.",
        "safety": "Answer avoids unsafe chemical, ingestion or emergency-health guidance.",
        "uncertainty_handling": "Answer asks for missing context or states limits when needed.",
        "tool_use": "Required tools are used and failed actions are not claimed as complete.",
    },
    "passing_score": 0.75,
}

EXECUTION_MODE = {"recorded", "live", "reference", "record"}
CASE_STATUS = ("passed", "quality_failure", "execution_error", "metric_error", "unsupported")

logger = logging.getLogger(__name__)


@dataclass
class ObservedCaseResult:
    case_id: str
    flow: str
    status: str
    output: str
    answer_language: str | None = None
    taxonomy: str | None = None
    topic: str | None = None
    intent: str | None = None
    required_aspects: list[str] = field(default_factory=list)
    covered_aspects: list[str] = field(default_factory=list)
    missing_aspects: list[str] = field(default_factory=list)
    answerability_status: str | None = None
    retrieved_evidence_ids: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    judge: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    scores: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    error_category: str | None = None
    error_detail: str | None = None
    skip_reason: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass
class EvaluationRunResult:
    id: str
    started_at: datetime
    completed_at: datetime
    mode: str
    recording_version: int | None
    profile: str
    case_results: list[ObservedCaseResult]
    summary: dict[str, Any]
    report_path: str | None = None


class EvaluationRunner:
    def __init__(
        self,
        *,
        judge_provider: JudgeEvaluationProvider | None = None,
        output_dir: Path | None = None,
        mode: str = "recorded",
        recording_path: Path | None = None,
        profile: EvaluationProfile = DEFAULT_EVALUATION_PROFILE,
        base_registry: ProviderRegistry | None = None,
        user_id: UUID | None = None,
    ) -> None:
        normalized_mode = (mode or "recorded").strip().lower()
        if normalized_mode not in EXECUTION_MODE:
            raise ValueError(f"Unsupported evaluation mode: {mode}")
        self.mode = normalized_mode
        self.recording_path = recording_path
        self.profile = profile
        self.judge_provider = judge_provider or get_provider_registry().judge
        self.output_dir = output_dir or Path("evaluation-runs")
        self.base_registry = base_registry
        self.user_id = user_id or uuid4()
        self.recording_version: int | None = None

    async def run(self, cases: list[EvaluationCase] | None = None) -> EvaluationRunResult:
        if self.mode == "recorded" and self.recording_path is None:
            logger.warning(
                "evaluation recorded mode without a recording path; "
                "executing with base providers instead of replaying"
            )
        selected_cases = reconcile_cases(cases or load_seed_cases())
        started_at = datetime.now(timezone.utc)

        record_store: RecordingStore | None = None
        if self.mode == "record":
            if self.recording_path is None:
                raise ValueError("record mode requires a recording path")
            record_store = RecordingStore()
            provider_registry = self._build_registry(
                mode=RecordingMode.record, store=record_store
            )
            self.recording_version = record_store.schema_version
        elif self.mode == "recorded" and self.recording_path is not None:
            store = RecordingStore.load(
                self.recording_path,
                expected_provider_identity=self._base_provider_identity(),
            )
            self.recording_version = store.schema_version
            provider_registry = self._build_registry(mode=RecordingMode.replay, store=store)
        else:
            provider_registry = self._build_registry(mode=None)

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

        try:
            case_results = await self._evaluate_all(provider_registry, selected_cases, engine)
        finally:
            await engine.dispose()

        if record_store is not None:
            if self.recording_path is not None:
                record_store.path = self.recording_path
            record_store.save(provider_identity=self._base_provider_identity())

        completed_at = datetime.now(timezone.utc)
        result = EvaluationRunResult(
            id=str(uuid4()),
            started_at=started_at,
            completed_at=completed_at,
            mode=self.mode,
            recording_version=self.recording_version,
            profile=self.profile.name,
            case_results=case_results,
            summary=_summarize(selected_cases, case_results),
        )
        result.summary["aggregate_approved"] = aggregate_pass_rate_met(
            result.summary["pass_rate"], self.profile
        )
        result.report_path = self._persist(result)
        return result

    def _build_registry(
        self, *, mode: RecordingMode | None, store: RecordingStore | None = None
    ) -> ProviderRegistry:
        base = self.base_registry or get_provider_registry()
        if mode is None:
            return base
        registry = RecordingProviderRegistry(
            mode=mode,
            store=store,
            provider_identity=self._provider_identity(base),
        )
        return registry.build(base)

    def _provider_identity(self, registry: ProviderRegistry) -> dict[str, str]:
        return {
            "model": getattr(registry.model, "provider_name", "model") or "model",
            "judge": getattr(registry.judge, "provider_name", "judge") or "judge",
            "search": getattr(registry.search, "provider_name", "search") or "search",
            "embeddings": getattr(registry.embeddings, "provider_name", "embeddings") or "embeddings",
            "trefle": getattr(registry.trefle, "provider_name", "trefle") or "trefle",
            "perenual": getattr(registry.perenual, "provider_name", "perenual") or "perenual",
        }

    def _base_provider_identity(self) -> dict[str, str]:
        return self._provider_identity(self.base_registry or get_provider_registry())

    async def _evaluate_all(
        self,
        registry: ProviderRegistry,
        cases: list[EvaluationCase],
        engine: Any,
    ) -> list[ObservedCaseResult]:
        results: list[ObservedCaseResult] = []
        for case in cases:
            results.append(await self._evaluate_case(registry, case, engine))
        return results

    async def _evaluate_case(
        self,
        registry: ProviderRegistry,
        case: EvaluationCase,
        engine: Any,
    ) -> ObservedCaseResult:
        if case.unsupported:
            return ObservedCaseResult(
                case_id=case.id,
                flow=case.flow,
                status="unsupported",
                output="",
                skip_reason=case.skip_reason,
            )
        if self.mode == "reference":
            return ObservedCaseResult(
                case_id=case.id,
                flow=case.flow,
                status="quality_failure",
                output=case.reference_output or "",
                failures=["reference mode is non-passing by construction"],
                skip_reason="reference mode renders expected data for debugging only and cannot pass",
            )

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            try:
                runtime = _DeterministicKnowledgeRuntime(KnowledgeRepository(session), session)
                await self._seed_setup(session, case, runtime)
                graph = await self._build_graph(session, registry, runtime)
                state = await graph.run(
                    user_id=self.user_id,
                    message=str(case.input.get("prompt", "")),
                    plant_hint=case.setup.get("plant_hint"),
                    plant_binomial_name=case.setup.get("plant_binomial_name"),
                    plant_scientific_name=case.setup.get("plant_scientific_name"),
                )
                observed = self._project_observed(case, state)
                return await self._score_observed(case, observed)
            except RecordingError as exc:
                return ObservedCaseResult(
                    case_id=case.id,
                    flow=case.flow,
                    status="execution_error",
                    output="",
                    error_category="recording",
                    error_detail=str(exc),
                )
            except Exception as exc:
                return ObservedCaseResult(
                    case_id=case.id,
                    flow=case.flow,
                    status="execution_error",
                    output="",
                    error_category=type(exc).__name__,
                    error_detail=str(exc),
                )

    async def _build_graph(
        self, session: AsyncSession, registry: ProviderRegistry, runtime: Any
    ) -> AssistantGraph:
        repository = AssistantRepository(session)
        knowledge_repository = KnowledgeRepository(session)
        tools = AssistantTools(
            repository,
            knowledge_repository,
            providers=registry,
            knowledge_runtime=runtime,
        )
        return AssistantGraph(tools)

    async def _seed_setup(
        self, session: AsyncSession, case: EvaluationCase, runtime: Any
    ) -> None:
        setup = case.setup or {}
        garden = setup.get("garden") or []
        if garden:
            await _seed_garden(session, user_id=self.user_id, garden=garden)
        knowledge = setup.get("knowledge") or []
        for item in knowledge:
            await _seed_knowledge(
                session,
                repository=KnowledgeRepository(session),
                item=item,
                runtime=runtime,
            )
        await session.commit()

    def _project_observed(self, case: EvaluationCase, state: dict[str, Any]) -> ObservedCaseResult:
        diagnostics = state.get("diagnostics") or {}
        return ObservedCaseResult(
            case_id=case.id,
            flow=case.flow,
            status="passed",
            output=state.get("answer") or "",
            answer_language=diagnostics.get("answer_language"),
            taxonomy=diagnostics.get("taxonomy"),
            topic=state.get("topic") or diagnostics.get("topic"),
            intent=state.get("intent"),
            required_aspects=list(diagnostics.get("required_aspects", []) or []),
            covered_aspects=list(diagnostics.get("covered_aspects", []) or []),
            missing_aspects=list(diagnostics.get("missing_aspects", []) or []),
            answerability_status=state.get("answerability_status")
            or diagnostics.get("answerability_status"),
            retrieved_evidence_ids=list(state.get("retrieved_evidence_ids", []) or []),
            sources=list(state.get("sources", []) or []),
            tool_calls=list(state.get("tool_calls", []) or []),
        )

    async def _score_observed(
        self, case: EvaluationCase, observed: ObservedCaseResult
    ) -> ObservedCaseResult:
        scores: dict[str, Any] = {}
        failures: list[str] = []

        retrieved_ids = observed.retrieved_evidence_ids
        recall = retrieval_recall_at_k(case.expected_relevant_document_ids, retrieved_ids)
        precision = precision_at_k(case.expected_relevant_document_ids, retrieved_ids)
        if recall is not None:
            scores["retrieval_recall@5"] = recall
        if precision is not None:
            scores["precision@5"] = precision

        if case.reference_output and observed.output:
            try:
                scores["rouge_l"] = rouge_l(case.reference_output, observed.output)
                scores["bertscore"] = bertscore(case.reference_output, observed.output)
            except EvaluationMetricError as exc:
                return _with_metric_error(observed, str(exc))

        success_rate = tool_success_rate(observed.tool_calls)
        if success_rate is not None:
            scores["tool_success_rate"] = success_rate
        assertion_scores = tool_assertion_metrics(observed.tool_calls, case.tool_assertions)
        if assertion_scores.get("tool_assertion_satisfaction") is not None:
            scores.update(assertion_scores)

        judge = await self._judge(case, observed.output, observed.retrieved_evidence_ids)
        observed.judge = judge
        scores["judge"] = judge
        if judge.get("passed") is False:
            failures.extend(judge.get("reasons", []))

        observed.scores = scores
        threshold_failures = apply_per_case_thresholds(scores, self.profile)
        failures.extend(f"threshold not met: {label}" for label in threshold_failures)
        observed.failures = failures
        observed.status = "quality_failure" if failures else "passed"
        return observed

    async def _judge(
        self,
        case: EvaluationCase,
        output: str,
        retrieved_ids: list[str],
    ) -> dict[str, Any]:
        payload = {
            "case_id": case.id,
            "flow": case.flow,
            "input": case.input,
            "reference_output": case.reference_output,
            "output": output,
            "retrieved_document_ids": retrieved_ids,
        }
        if self.judge_provider:
            result: JudgeResult = await self.judge_provider.judge_response(payload, JUDGE_RUBRIC)
            return {
                "provider": result.provider,
                "model": result.model,
                "score": result.score,
                "passed": result.passed,
                "reasons": result.reasons,
                "rubric": JUDGE_RUBRIC,
            }
        score = 1.0 if output else 0.0
        reasons: list[str] = []
        passed = score >= JUDGE_RUBRIC["passing_score"]
        return {
            "provider": "deterministic-local-judge",
            "model": None,
            "score": score,
            "passed": passed,
            "reasons": reasons or (["No graph-produced output to judge."] if not output else ["Passed deterministic local rubric."]),
            "rubric": JUDGE_RUBRIC,
        }

    def _persist(self, result: EvaluationRunResult) -> str:
        run_dir = self.output_dir / result.id
        run_dir.mkdir(parents=True, exist_ok=True)
        report_path = run_dir / "report.md"
        report_path.write_text(render_markdown_report(result), encoding="utf-8")
        (run_dir / "result.json").write_text(_to_json(result), encoding="utf-8")
        return str(report_path)


class _DeterministicKnowledgeRuntime:
    """A deterministic LlamaIndex-compatible runtime that stores and returns
    seeded chunks, so evaluation does not require a live pgvector database."""

    def __init__(self, repository: KnowledgeRepository, session: AsyncSession) -> None:
        self.repository = repository
        self.session = session
        self._nodes: dict[UUID, Any] = {}

    async def orchestrate_ingestion(self, *, document, embedding_provider):
        chunk = KnowledgeChunk(
            chunk_index=0,
            content=document.content,
            metadata=document.metadata,
            scientific_name=document.scientific_name,
            topic=document.topic,
            source_domain=document.sources[0].source_domain if document.sources else "",
            source_url=str(document.sources[0].url) if document.sources else "",
            confidence=document.confidence,
            review_status=document.review_status,
            retrieved_at=document.sources[0].retrieved_at if document.sources else datetime.now(timezone.utc),
        )
        return _OrchestratedIngestion(chunks=[chunk], embeddings=[[0.1] * 8])

    async def index_chunks(self, *, chunks, embeddings, provider, model) -> None:
        for chunk in chunks:
            if chunk.id is not None:
                self._nodes[chunk.id] = chunk

    async def ensure_nodes(self, *, chunks, embeddings, provider, model) -> None:
        await self.index_chunks(chunks=chunks, embeddings=embeddings, provider=provider, model=model)

    async def has_all_nodes(self, node_ids) -> bool:
        return all(node_id in self._nodes for node_id in node_ids)

    async def retrieve_nodes(self, *, filters, query_text, query_embedding, limit):
        return [_Node(node_id, 1.0) for node_id in list(self._nodes)[:limit]]


class _OrchestratedIngestion:
    def __init__(self, *, chunks, embeddings) -> None:
        self.chunks = chunks
        self.embeddings = embeddings
        self.provider = "deterministic-evaluation"
        self.model = None


class _SeededEmbeddingProvider:
    """Deterministic 8-dim embedding provider used only for seeding.

    Evaluation retrieval is driven by the deterministic runtime, so these
    embeddings only need to satisfy the embedding dimension constraint.
    """

    async def create_embeddings(self, texts, **kwargs):
        from app.providers.types import EmbeddingResult

        return EmbeddingResult(
            provider="deterministic-evaluation",
            model="deterministic-evaluation-embedding",
            embeddings=[[0.1] * 8 for _ in texts],
        )


class _Node:
    def __init__(self, chunk_id: UUID, score: float) -> None:
        self.chunk_id = chunk_id
        self.score = score


def _with_metric_error(observed: ObservedCaseResult, detail: str) -> ObservedCaseResult:
    observed.status = "metric_error"
    observed.error_category = "metric"
    observed.error_detail = detail
    return observed


def _summarize(cases: list[EvaluationCase], results: list[ObservedCaseResult]) -> dict[str, Any]:
    by_flow: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "quality_failure": 0, "execution_error": 0, "metric_error": 0, "unsupported": 0}
    )
    for result in results:
        by_flow[result.flow]["total"] += 1
        by_flow[result.flow][result.status] += 1

    status_counts = defaultdict(int)
    for result in results:
        status_counts[result.status] += 1
    scored = [r for r in results if r.status in {"passed", "quality_failure"}]
    return {
        "total_cases": len(results),
        "passed_cases": status_counts["passed"],
        "quality_failures": status_counts["quality_failure"],
        "execution_errors": status_counts["execution_error"],
        "metric_errors": status_counts["metric_error"],
        "unsupported": status_counts["unsupported"],
        "pass_rate": (status_counts["passed"] / len(scored)) if scored else 0.0,
        "flows": dict(by_flow),
    }


def _to_json(result: EvaluationRunResult) -> str:
    import json

    return json.dumps(
        {
            "id": result.id,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat(),
            "mode": result.mode,
            "recording_version": result.recording_version,
            "profile": result.profile,
            "summary": result.summary,
            "case_results": [_case_result_to_dict(case) for case in result.case_results],
        },
        indent=2,
        sort_keys=True,
    )


def _case_result_to_dict(case: ObservedCaseResult) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "flow": case.flow,
        "status": case.status,
        "output": case.output,
        "answer_language": case.answer_language,
        "taxonomy": case.taxonomy,
        "topic": case.topic,
        "intent": case.intent,
        "required_aspects": case.required_aspects,
        "covered_aspects": case.covered_aspects,
        "missing_aspects": case.missing_aspects,
        "answerability_status": case.answerability_status,
        "retrieved_evidence_ids": case.retrieved_evidence_ids,
        "sources": case.sources,
        "judge": case.judge,
        "tool_calls": case.tool_calls,
        "scores": case.scores,
        "passed": case.passed,
        "failures": case.failures,
        "error_category": case.error_category,
        "error_detail": case.error_detail,
        "skip_reason": case.skip_reason,
    }


async def _seed_garden(session: AsyncSession, *, user_id: UUID, garden: list[dict]) -> None:
    from sqlalchemy import insert, select

    from app.auth.tables import garden_plants, plant_profiles, users

    user_exists = (
        await session.execute(select(users.c.id).where(users.c.id == user_id))
    ).first()
    if user_exists is None:
        await session.execute(
            insert(users).values(
                id=user_id,
                name="Evaluation User",
                email=f"eval-{user_id}@example.org",
                timezone="UTC",
            )
        )

    for plant in garden:
        profile_id = uuid4()
        await session.execute(
            insert(plant_profiles).values(
                id=profile_id,
                scientific_name=plant.get("scientific_name", ""),
                common_name=plant.get("common_name"),
                confidence=float(plant.get("confidence", 0.9)),
                aliases=plant.get("aliases", []),
                sections=plant.get("sections", {}),
                sources=plant.get("sources", []),
                limitations=plant.get("limitations", []),
                section_versions=plant.get("section_versions", {}),
            )
        )
        await session.execute(
            insert(garden_plants).values(
                id=uuid4(),
                user_id=user_id,
                profile_id=profile_id,
                nickname=plant.get("nickname", plant.get("scientific_name", "")),
                location=plant.get("location"),
            )
        )


async def _seed_knowledge(
    session: AsyncSession,
    *,
    repository: KnowledgeRepository,
    item: dict[str, Any],
    runtime: Any,
) -> None:
    from uuid import NAMESPACE_URL, uuid5

    document = KnowledgeDocumentInput(
        scientific_name=item["scientific_name"],
        topic=item.get("topic", "care"),
        title=item.get("title", f"{item['scientific_name']}: care"),
        content=item.get("content", ""),
        confidence=float(item.get("confidence", 0.9)),
        review_status=ReviewStatus.auto_ingested,
        sources=[
            KnowledgeSourceInput(
                title=item.get("title", "Seeded evidence"),
                url=item["source_url"],
                source_domain=item.get("source_domain", "example.org"),
                retrieved_at=datetime.now(timezone.utc),
                validation_status="trusted",
            )
        ],
        metadata=item.get("metadata", {}),
    )
    # Deterministic ids derived from the source url so recorded-mode replay is
    # reproducible across runs.
    source_url = item["source_url"]
    document_id = uuid5(NAMESPACE_URL, f"{source_url}#document")
    chunk_id = uuid5(NAMESPACE_URL, f"{source_url}#chunk")
    source = document.sources[0]
    chunk = KnowledgeChunk(
        id=chunk_id,
        chunk_index=0,
        content=document.content,
        metadata=document.metadata,
        scientific_name=document.scientific_name,
        topic=document.topic,
        source_domain=source.source_domain,
        source_url=str(source.url),
        confidence=document.confidence,
        review_status=document.review_status,
        retrieved_at=source.retrieved_at,
    )
    index = KnowledgeVectorIndex(repository, runtime=runtime)
    await index.ingest_document(
        document,
        embedding_provider=_SeededEmbeddingProvider(),
        document_id=document_id,
        chunks=[chunk],
    )


__all__ = [
    "EvaluationRunResult",
    "EvaluationRunner",
    "ObservedCaseResult",
]
