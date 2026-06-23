from dataclasses import dataclass, field
from time import perf_counter


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

    def record_request(self, latency_seconds: float, failed: bool) -> None:
        self.requests_total += 1
        self.request_latency_seconds.append(latency_seconds)
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

        provider_failure_lines = [
            (
                "fotosintesis_provider_failures_total"
                f'{{role="{_escape_prometheus_label_value(role)}",'
                f'provider="{_escape_prometheus_label_value(provider)}",'
                f'operation="{_escape_prometheus_label_value(operation)}",'
                f'failure_category="{_escape_prometheus_label_value(failure_category)}"}} {count}'
            )
            for (role, provider, operation, failure_category), count
            in sorted(self.provider_failure_counts.items())
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
                "",
            ]
        )


def _escape_prometheus_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


metrics_registry = MetricsRegistry()


class Timer:
    def __enter__(self) -> "Timer":
        self.started_at = perf_counter()
        self.elapsed = 0.0
        return self

    def __exit__(self, *args: object) -> None:
        self.elapsed = perf_counter() - self.started_at
