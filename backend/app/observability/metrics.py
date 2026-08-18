import time
from dataclasses import dataclass, field

from app.jobs.schemas import JobFailureCategory, JobStatus, JobType
from app.limiter.policy import EndpointCategory, LimiterOutcome

JOB_DURATION_BUCKETS: tuple[float, ...] = (
    0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0,
)

ENRICHMENT_COUNT_BUCKETS: tuple[float, ...] = (
    0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 12.0, 17.0,
)

ENRICHMENT_LIFECYCLE_OUTCOMES = frozenset(
    {"complete", "partial", "failed"}
)

ENRICHMENT_POLICY_LABELS = frozenset({"1", "unsupported"})

_JOB_TYPES = frozenset(item.value for item in JobType)
_OUTCOME_STATUSES = frozenset(item.value for item in JobStatus) | {
    "retry_scheduled",
    "lease_lost",
    "cancelled",
}
_FAILURE_CATEGORIES = frozenset(item.value for item in JobFailureCategory)
_RECOVERY_OUTCOMES = frozenset({"lease_expired", "attempts_exhausted"})
_BACKLOG_STATUSES = frozenset({JobStatus.pending.value, JobStatus.processing.value})
_JOB_STATUSES = frozenset(item.value for item in JobStatus)
_SCHEDULE_OUTCOMES = frozenset({"created", "reused"})
_LIMITER_CATEGORIES = frozenset(item.value for item in EndpointCategory)
_LIMITER_OUTCOMES = frozenset(item.value for item in LimiterOutcome)
_REMINDER_SUGGESTION_OUTCOMES = frozenset(
    {"accepted", "edited", "rejected", "clarified", "duplicate"}
)


def _require_closed_label(*, name: str, value: str, allowed: frozenset[str]) -> None:
    if value not in allowed:
        raise ValueError(f"unsupported {name} metric label: {value!r}")


@dataclass
class Histogram:
    """Bounded histogram with fixed bucket boundaries.

    ``observe`` records one sample. Memory usage is O(buckets) per registered
    label tuple, regardless of how many observations are recorded, because
    individual samples are not retained.
    """

    buckets: tuple[float, ...] = JOB_DURATION_BUCKETS
    counts: list[int] = field(default_factory=list)
    total_count: int = 0
    total_sum: float = 0.0

    def __post_init__(self) -> None:
        if not self.counts:
            self.counts = [0] * (len(self.buckets) + 1)

    def observe(self, value: float) -> None:
        self.total_count += 1
        self.total_sum += value
        for index, upper_bound in enumerate(self.buckets):
            if value <= upper_bound:
                self.counts[index] += 1
                return
        self.counts[-1] += 1

    def render(self, *, name: str, label_pairs: tuple[tuple[str, str], ...]) -> str:
        labels = ",".join(f'{k}="{_escape(v)}"' for k, v in label_pairs)
        lines: list[str] = []
        running = 0
        for index, upper in enumerate(self.buckets):
            running += self.counts[index]
            le = f"{upper}"
            if labels:
                le_label = ",".join(f'{k}="{_escape(v)}"' for k, v in label_pairs + (("le", le),))
                lines.append(f'{name}_bucket{{{le_label}}} {running}')
            else:
                lines.append(f'{name}_bucket{{le="{le}"}} {running}')
        if labels:
            inf_label = ",".join(f'{k}="{_escape(v)}"' for k, v in label_pairs + (("le", "+Inf"),))
            lines.append(f"{name}_bucket{{{inf_label}}} {self.total_count}")
        else:
            lines.append(f'{name}_bucket{{le="+Inf"}} {self.total_count}')
        label_text = f"{{{labels}}}" if labels else ""
        lines.append(f"{name}_count{label_text} {self.total_count}")
        lines.append(f"{name}_sum{label_text} {self.total_sum:.6f}")
        return "\n".join(lines)


def _escape_prometheus_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


_escape = _escape_prometheus_label_value


@dataclass(frozen=True)
class EnrichmentEfficacyTotals:
    """Database-derived snapshot of durable enrichment efficacy telemetry.

    ``counts`` keys are ``(policy_label, lifecycle_outcome, acquisition_avoided)``
    and ``histograms`` keys are ``(observation_name, policy_label, lifecycle_outcome)``.
    Multiple replicas expose identical database-derived totals, so monitoring
    must aggregate with max, not sum.
    """

    counts: dict[tuple[str, str, bool], int]
    histograms: dict[tuple[str, str, str], Histogram]


@dataclass
class MetricsRegistry:
    requests_total: int = 0
    requests_failed: int = 0
    provider_calls_total: int = 0
    tool_runs_total: int = 0
    request_latency_seconds: list[float] = field(default_factory=list)
    fallback_attempts_total: int = 0
    fallback_successes_total: int = 0
    provider_failures_total: int = 0
    provider_failure_counts: dict[tuple[str, str, str, str], int] = field(default_factory=dict)
    skipped_unhealthy_providers_total: int = 0
    circuit_breaker_opens_total: int = 0
    classifier_invalid_output_total: int = 0
    job_claims_total: int = 0
    job_claims_by_type: dict[str, int] = field(default_factory=dict)
    job_outcomes: dict[tuple[str, str], int] = field(default_factory=dict)
    job_duration_histograms: dict[tuple[str, str], Histogram] = field(default_factory=dict)
    job_retries_by_type_category: dict[tuple[str, str], int] = field(default_factory=dict)
    job_stale_recoveries_by_type: dict[tuple[str, str], int] = field(default_factory=dict)
    job_backlog_by_type_status: dict[tuple[str, str], int] = field(default_factory=dict)
    job_status_by_type: dict[tuple[str, str], int] = field(default_factory=dict)
    job_schedules_by_type_outcome: dict[tuple[str, str], int] = field(
        default_factory=dict
    )
    enrichment_acquisition_avoided_total: int = 0
    enrichment_partial_outcomes_total: int = 0
    enrichment_completion_time: Histogram = field(default_factory=Histogram)
    enrichment_efficacy_counts: dict[tuple[str, str, bool], int] = field(
        default_factory=dict
    )
    enrichment_efficacy_histograms: dict[tuple[str, str, str], Histogram] = field(
        default_factory=dict
    )
    job_oldest_eligible_age_seconds: float | None = None
    worker_last_successful_poll_timestamp_seconds: float | None = None
    request_latency_seconds_max_samples: int = 10_000
    limiter_outcomes: dict[tuple[str, str], int] = field(default_factory=dict)
    reminder_suggestion_outcomes: dict[str, int] = field(default_factory=dict)

    def record_reminder_suggestion_outcome(self, *, outcome: str) -> None:
        _require_closed_label(
            name="outcome",
            value=outcome,
            allowed=_REMINDER_SUGGESTION_OUTCOMES,
        )
        self.reminder_suggestion_outcomes[outcome] = (
            self.reminder_suggestion_outcomes.get(outcome, 0) + 1
        )

    def record_job_claim(self, *, job_type: str) -> None:
        _require_closed_label(name="job_type", value=job_type, allowed=_JOB_TYPES)
        self.job_claims_total += 1
        self.job_claims_by_type[job_type] = self.job_claims_by_type.get(job_type, 0) + 1

    def record_job_outcome(
        self, *, job_type: str, status: str, duration_seconds: float,
    ) -> None:
        _require_closed_label(name="job_type", value=job_type, allowed=_JOB_TYPES)
        _require_closed_label(name="status", value=status, allowed=_OUTCOME_STATUSES)
        key = (job_type, status)
        self.job_outcomes[key] = self.job_outcomes.get(key, 0) + 1
        histogram = self.job_duration_histograms.get(key)
        if histogram is None:
            histogram = Histogram()
            self.job_duration_histograms[key] = histogram
        histogram.observe(duration_seconds)
        if status == "retry_scheduled":
            # category label is added explicitly via record_job_retry
            pass

    def record_job_retry(self, *, job_type: str, category: str) -> None:
        _require_closed_label(name="job_type", value=job_type, allowed=_JOB_TYPES)
        _require_closed_label(
            name="category", value=category, allowed=_FAILURE_CATEGORIES
        )
        key = (job_type, category)
        self.job_retries_by_type_category[key] = self.job_retries_by_type_category.get(key, 0) + 1

    def record_job_stale_recovery(
        self, *, job_type: str, outcome: str, count: int = 1
    ) -> None:
        _require_closed_label(name="job_type", value=job_type, allowed=_JOB_TYPES)
        _require_closed_label(name="outcome", value=outcome, allowed=_RECOVERY_OUTCOMES)
        key = (job_type, outcome)
        self.job_stale_recoveries_by_type[key] = (
            self.job_stale_recoveries_by_type.get(key, 0) + count
        )

    def record_job_backlog(self, *, job_type: str, status: str, count: int) -> None:
        _require_closed_label(name="job_type", value=job_type, allowed=_JOB_TYPES)
        _require_closed_label(name="status", value=status, allowed=_BACKLOG_STATUSES)
        key = (job_type, status)
        self.job_backlog_by_type_status[key] = count

    def record_job_status_count(
        self, *, job_type: str, status: str, count: int
    ) -> None:
        _require_closed_label(name="job_type", value=job_type, allowed=_JOB_TYPES)
        _require_closed_label(name="status", value=status, allowed=_JOB_STATUSES)
        self.job_status_by_type[(job_type, status)] = count

    def record_job_schedule(self, *, job_type: str, outcome: str) -> None:
        _require_closed_label(name="job_type", value=job_type, allowed=_JOB_TYPES)
        _require_closed_label(
            name="outcome", value=outcome, allowed=_SCHEDULE_OUTCOMES
        )
        key = (job_type, outcome)
        self.job_schedules_by_type_outcome[key] = (
            self.job_schedules_by_type_outcome.get(key, 0) + 1
        )

    def record_enrichment_completion(
        self,
        *,
        duration_seconds: float,
        acquisition_avoided: bool,
        partial: bool,
    ) -> None:
        self.enrichment_completion_time.observe(max(duration_seconds, 0.0))
        if acquisition_avoided:
            self.enrichment_acquisition_avoided_total += 1
        if partial:
            self.enrichment_partial_outcomes_total += 1

    def record_enrichment_efficacy(
        self,
        *,
        policy_label: str,
        lifecycle_outcome: str,
        acquisition_avoided: bool,
        local_covered_count: int,
        final_covered_count: int,
        coverage_gain: int,
        accepted_aspect_count: int,
        search_count: int,
        duration_seconds: float,
    ) -> None:
        """Record bounded terminal enrichment efficacy telemetry.

        Only closed enums, booleans, bounded count buckets, and the closed
        policy label are used; no taxonomy, source, claim, quote, or arbitrary
        policy value is accepted as a label.
        """
        _require_closed_label(
            name="policy_label",
            value=policy_label,
            allowed=ENRICHMENT_POLICY_LABELS,
        )
        _require_closed_label(
            name="lifecycle_outcome",
            value=lifecycle_outcome,
            allowed=ENRICHMENT_LIFECYCLE_OUTCOMES,
        )
        key = (policy_label, lifecycle_outcome, bool(acquisition_avoided))
        self.enrichment_efficacy_counts[key] = self.enrichment_efficacy_counts.get(key, 0) + 1
        observations = {
            "local_covered_count": float(max(0, local_covered_count)),
            "final_covered_count": float(max(0, final_covered_count)),
            "coverage_gain": float(coverage_gain),
            "accepted_aspect_count": float(max(0, accepted_aspect_count)),
            "search_count": float(max(0, search_count)),
            "completion_duration_seconds": max(duration_seconds, 0.0),
        }
        for name, value in observations.items():
            histogram_key = (name, policy_label, lifecycle_outcome)
            histogram = self.enrichment_efficacy_histograms.get(histogram_key)
            if histogram is None:
                histogram = Histogram(
                    buckets=(
                        ENRICHMENT_COUNT_BUCKETS
                        if name != "completion_duration_seconds"
                        else JOB_DURATION_BUCKETS
                    )
                )
                self.enrichment_efficacy_histograms[histogram_key] = histogram
            histogram.observe(value)

    def replace_enrichment_efficacy(self, totals: EnrichmentEfficacyTotals) -> None:
        """Replace the current efficacy snapshot with database-derived totals.

        This is a replacement, not an increment: repeated refreshes and worker
        restarts render the same totals because the durable observations are
        the single source of truth.
        """
        self.enrichment_efficacy_counts = dict(totals.counts)
        self.enrichment_efficacy_histograms = {
            key: Histogram(buckets=histogram.buckets, counts=list(histogram.counts), total_count=histogram.total_count, total_sum=histogram.total_sum)
            for key, histogram in totals.histograms.items()
        }

    def reset_job_backlog(self) -> None:
        self.job_backlog_by_type_status.clear()

    def reset_job_status_counts(self) -> None:
        self.job_status_by_type.clear()

    def record_oldest_eligible_age(self, *, age_seconds: float | None) -> None:
        self.job_oldest_eligible_age_seconds = age_seconds

    def record_worker_successful_poll(self, *, timestamp_seconds: float | None = None) -> None:
        self.worker_last_successful_poll_timestamp_seconds = (
            timestamp_seconds if timestamp_seconds is not None else time.time()
        )

    def record_limiter_outcome(
        self,
        *,
        category: EndpointCategory,
        outcome: LimiterOutcome,
    ) -> None:
        """Record one limiter decision with only closed labels."""
        _require_closed_label(name="category", value=category.value, allowed=_LIMITER_CATEGORIES)
        _require_closed_label(name="outcome", value=outcome.value, allowed=_LIMITER_OUTCOMES)
        key = (category.value, outcome.value)
        self.limiter_outcomes[key] = self.limiter_outcomes.get(key, 0) + 1

    def record_request(self, latency_seconds: float, failed: bool) -> None:
        self.requests_total += 1
        self.request_latency_seconds.append(latency_seconds)
        if len(self.request_latency_seconds) > self.request_latency_seconds_max_samples:
            self.request_latency_seconds = self.request_latency_seconds[
                -self.request_latency_seconds_max_samples:
            ]
        if failed:
            self.requests_failed += 1

    def record_provider_failure(
        self,
        *,
        role: str,
        provider: str,
        operation: str,
        failure_category: str,
    ) -> None:
        self.provider_failures_total += 1
        key = (role, provider, operation, failure_category)
        self.provider_failure_counts[key] = self.provider_failure_counts.get(key, 0) + 1

    def to_prometheus(self) -> str:
        average_latency = 0.0
        if self.request_latency_seconds:
            average_latency = sum(self.request_latency_seconds) / len(self.request_latency_seconds)

        sorted_outcomes = sorted(self.job_outcomes.items(), key=lambda x: (x[0][0], x[0][1]))
        job_outcome_lines = [
            (
                "fotosintesis_job_outcomes_total"
                f'{{job_type="{_escape(job_type)}",'
                f'status="{_escape(status)}"}} {count}'
            )
            for (job_type, status), count in sorted_outcomes
        ]

        sorted_retries = sorted(self.job_retries_by_type_category.items())
        retry_lines = [
            (
                "fotosintesis_job_retries_total"
                f'{{job_type="{_escape(job_type)}",'
                f'category="{_escape(category)}"}} {count}'
            )
            for (job_type, category), count in sorted_retries
        ]

        sorted_stale = sorted(self.job_stale_recoveries_by_type.items())
        stale_lines = [
            (
                "fotosintesis_job_stale_recoveries_total"
                f'{{job_type="{_escape(job_type)}",'
                f'outcome="{_escape(outcome)}"}} {count}'
            )
            for (job_type, outcome), count in sorted_stale
        ]

        sorted_claims_by_type = sorted(self.job_claims_by_type.items())
        claims_by_type_lines = [
            (
                "fotosintesis_job_claims_by_type_total"
                f'{{job_type="{_escape(job_type)}"}} {count}'
            )
            for job_type, count in sorted_claims_by_type
        ]

        sorted_backlog = sorted(self.job_backlog_by_type_status.items())
        backlog_lines = [
            (
                "fotosintesis_job_backlog_count"
                f'{{job_type="{_escape(job_type)}",'
                f'status="{_escape(status)}"}} {count}'
            )
            for (job_type, status), count in sorted_backlog
        ]

        status_lines = [
            (
                "fotosintesis_job_status_count"
                f'{{job_type="{_escape(job_type)}",'
                f'status="{_escape(status)}"}} {count}'
            )
            for (job_type, status), count in sorted(self.job_status_by_type.items())
        ]

        schedule_lines = [
            (
                "fotosintesis_job_schedules_total"
                f'{{job_type="{_escape(job_type)}",'
                f'outcome="{_escape(outcome)}"}} {count}'
            )
            for (job_type, outcome), count in sorted(
                self.job_schedules_by_type_outcome.items()
            )
        ]

        sorted_histograms = sorted(self.job_duration_histograms.items())
        histogram_lines = [
            histogram.render(
                name="fotosintesis_job_attempt_duration_seconds",
                label_pairs=(("job_type", jt), ("status", st)),
            )
            for (jt, st), histogram in sorted_histograms
        ]
        enrichment_completion_lines = self.enrichment_completion_time.render(
            name="fotosintesis_enrichment_completion_time_seconds",
            label_pairs=(),
        )

        efficacy_count_lines = [
            (
                "fotosintesis_enrichment_efficacy_total"
                f'{{policy_version="{_escape(str(policy_version))}",'
                f'lifecycle_outcome="{_escape(outcome)}",'
                f'acquisition_avoided="{str(avoided).lower()}"}} {count}'
            )
            for (policy_version, outcome, avoided), count in sorted(
                self.enrichment_efficacy_counts.items(),
                key=lambda item: (item[0][0], item[0][1], item[0][2]),
            )
        ]
        efficacy_histogram_lines = []
        histogram_names = sorted(
            {name for (name, _, _) in self.enrichment_efficacy_histograms}
        )
        for name in histogram_names:
            efficacy_histogram_lines.append(
                f"# TYPE fotosintesis_enrichment_efficacy_{name} histogram"
            )
            for (entry_name, policy_version, outcome), histogram in sorted(
                self.enrichment_efficacy_histograms.items()
            ):
                if entry_name != name:
                    continue
                efficacy_histogram_lines.append(
                    histogram.render(
                        name=f"fotosintesis_enrichment_efficacy_{name}",
                        label_pairs=(
                            ("policy_version", str(policy_version)),
                            ("lifecycle_outcome", outcome),
                        ),
                    )
                )

        age_line = (
            f"fotosintesis_job_oldest_eligible_age_seconds "
            f"{self.job_oldest_eligible_age_seconds:.6f}"
            if self.job_oldest_eligible_age_seconds is not None
            else "fotosintesis_job_oldest_eligible_age_seconds 0"
        )

        provider_failure_lines = [
            (
                "fotosintesis_provider_failures_total"
                f'{{role="{_escape(role)}",'
                f'provider="{_escape(provider)}",'
                f'operation="{_escape(operation)}",'
                f'failure_category="{_escape(failure_category)}"}} {count}'
            )
            for (role, provider, operation, failure_category), count
            in sorted(self.provider_failure_counts.items())
        ]

        successful_poll_line = (
            "fotosintesis_worker_last_successful_poll_timestamp_seconds "
            f"{self.worker_last_successful_poll_timestamp_seconds:.6f}"
            if self.worker_last_successful_poll_timestamp_seconds is not None
            else "fotosintesis_worker_last_successful_poll_timestamp_seconds 0"
        )

        sorted_limiter_outcomes = sorted(self.limiter_outcomes.items())
        limiter_outcome_lines = [
            (
                "fotosintesis_limiter_outcomes_total"
                f'{{category="{_escape(category)}",'
                f'outcome="{_escape(outcome)}"}} {count}'
            )
            for (category, outcome), count in sorted_limiter_outcomes
        ]

        sorted_suggestion_outcomes = sorted(self.reminder_suggestion_outcomes.items())
        suggestion_outcome_lines = [
            (
                "fotosintesis_reminder_suggestion_outcomes_total"
                f'{{outcome="{_escape(outcome)}"}} {count}'
            )
            for outcome, count in sorted_suggestion_outcomes
        ]

        return "\n".join(
            [
                "# HELP fotosintesis_requests_total Total HTTP requests handled.",
                "# TYPE fotosintesis_requests_total counter",
                f"fotosintesis_requests_total {self.requests_total}",
                "# HELP fotosintesis_requests_failed_total Total failed HTTP requests.",
                "# TYPE fotosintesis_requests_failed_total counter",
                f"fotosintesis_requests_failed_total {self.requests_failed}",
                "# HELP fotosintesis_provider_calls_total Total provider calls.",
                "# TYPE fotosintesis_provider_calls_total counter",
                f"fotosintesis_provider_calls_total {self.provider_calls_total}",
                "# HELP fotosintesis_tool_runs_total Total agent tool runs.",
                "# TYPE fotosintesis_tool_runs_total counter",
                f"fotosintesis_tool_runs_total {self.tool_runs_total}",
                "# HELP fotosintesis_request_latency_seconds_avg Average HTTP latency.",
                "# TYPE fotosintesis_request_latency_seconds_avg gauge",
                f"fotosintesis_request_latency_seconds_avg {average_latency:.6f}",
                "# HELP fotosintesis_fallback_attempts_total Total provider fallback attempts.",
                "# TYPE fotosintesis_fallback_attempts_total counter",
                f"fotosintesis_fallback_attempts_total {self.fallback_attempts_total}",
                "# HELP fotosintesis_fallback_successes_total Total successful fallback completions.",
                "# TYPE fotosintesis_fallback_successes_total counter",
                f"fotosintesis_fallback_successes_total {self.fallback_successes_total}",
                "# HELP fotosintesis_provider_failures_total Total provider failures.",
                "# TYPE fotosintesis_provider_failures_total counter",
                f"fotosintesis_provider_failures_total {self.provider_failures_total}",
                *provider_failure_lines,
                "# HELP fotosintesis_skipped_unhealthy_providers_total Total skipped unhealthy providers.",
                "# TYPE fotosintesis_skipped_unhealthy_providers_total counter",
                f"fotosintesis_skipped_unhealthy_providers_total {self.skipped_unhealthy_providers_total}",
                "# HELP fotosintesis_circuit_breaker_opens_total Total circuit breaker opens.",
                "# TYPE fotosintesis_circuit_breaker_opens_total counter",
                f"fotosintesis_circuit_breaker_opens_total {self.circuit_breaker_opens_total}",
                "# HELP fotosintesis_classifier_invalid_output_total Total classifier invalid output events.",
                "# TYPE fotosintesis_classifier_invalid_output_total counter",
                f"fotosintesis_classifier_invalid_output_total {self.classifier_invalid_output_total}",
                "# HELP fotosintesis_job_claims_total Total job claims by workers.",
                "# TYPE fotosintesis_job_claims_total counter",
                f"fotosintesis_job_claims_total {self.job_claims_total}",
                *claims_by_type_lines,
                *job_outcome_lines,
                *retry_lines,
                *stale_lines,
                "# HELP fotosintesis_job_schedules_total Durable job scheduling outcomes.",
                "# TYPE fotosintesis_job_schedules_total counter",
                *schedule_lines,
                *backlog_lines,
                "# HELP fotosintesis_job_status_count Durable job rows by lifecycle status.",
                "# TYPE fotosintesis_job_status_count gauge",
                *status_lines,
                "# HELP fotosintesis_job_oldest_eligible_age_seconds Oldest eligible pending job age.",
                "# TYPE fotosintesis_job_oldest_eligible_age_seconds gauge",
                age_line,
                "# HELP fotosintesis_worker_last_successful_poll_timestamp_seconds Unix timestamp of the last successful worker database poll.",
                "# TYPE fotosintesis_worker_last_successful_poll_timestamp_seconds gauge",
                successful_poll_line,
                "# HELP fotosintesis_job_attempt_duration_seconds Histogram of job attempt duration in seconds.",
                "# TYPE fotosintesis_job_attempt_duration_seconds histogram",
                *histogram_lines,
                "# HELP fotosintesis_enrichment_acquisition_avoided_total Enrichment runs completed without external acquisition.",
                "# TYPE fotosintesis_enrichment_acquisition_avoided_total counter",
                f"fotosintesis_enrichment_acquisition_avoided_total {self.enrichment_acquisition_avoided_total}",
                "# HELP fotosintesis_enrichment_partial_outcomes_total Enrichment runs with a durable partial outcome.",
                "# TYPE fotosintesis_enrichment_partial_outcomes_total counter",
                f"fotosintesis_enrichment_partial_outcomes_total {self.enrichment_partial_outcomes_total}",
                "# HELP fotosintesis_enrichment_completion_time_seconds End-to-end time from durable enqueue to complete or partial enrichment.",
                "# TYPE fotosintesis_enrichment_completion_time_seconds histogram",
                enrichment_completion_lines,
                "# HELP fotosintesis_enrichment_efficacy_total Terminal enrichment runs by bounded outcome labels.",
                "# TYPE fotosintesis_enrichment_efficacy_total counter",
                *efficacy_count_lines,
                "# HELP fotosintesis_enrichment_efficacy_* Bounded coverage and search-count distributions per terminal enrichment outcome.",
                *efficacy_histogram_lines,
                "# HELP fotosintesis_limiter_outcomes_total Authentication limiter decisions by closed category and outcome.",
                "# TYPE fotosintesis_limiter_outcomes_total counter",
                *limiter_outcome_lines,
                "# HELP fotosintesis_reminder_suggestion_outcomes_total Reminder suggestion interaction outcomes.",
                "# TYPE fotosintesis_reminder_suggestion_outcomes_total counter",
                *suggestion_outcome_lines,
                "",
            ]
        )


metrics_registry = MetricsRegistry()
