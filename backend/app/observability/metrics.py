from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class MetricsRegistry:
    requests_total: int = 0
    requests_failed: int = 0
    provider_calls_total: int = 0
    tool_runs_total: int = 0
    request_latency_seconds: list[float] = field(default_factory=list)

    def record_request(self, latency_seconds: float, failed: bool) -> None:
        self.requests_total += 1
        self.request_latency_seconds.append(latency_seconds)
        if failed:
            self.requests_failed += 1

    def to_prometheus(self) -> str:
        average_latency = 0.0
        if self.request_latency_seconds:
            average_latency = sum(self.request_latency_seconds) / len(self.request_latency_seconds)

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
                "",
            ]
        )


metrics_registry = MetricsRegistry()


class Timer:
    def __enter__(self) -> "Timer":
        self.started_at = perf_counter()
        self.elapsed = 0.0
        return self

    def __exit__(self, *args: object) -> None:
        self.elapsed = perf_counter() - self.started_at
