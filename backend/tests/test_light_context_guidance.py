from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.assistant.graph import AssistantGraph
from app.core.settings import Settings
from tests._assistant_helpers import CONFIRMED_BINOMIAL, FakeTools

WATERING_CLASSIFIER = {
    "language": "es",
    "answer_language": "es",
    "intent": "plant_care_question",
    "topic": "watering",
    "required_aspects": ["watering_frequency_or_trigger"],
    "plant_reference": "Pata",
    "confidence": 0.92,
    "needs_retrieval": True,
}


def _measurement(*, reliability: str = "high", source: str = "sensor", age_days: int = 1) -> dict:
    return {
        "classification": "media",
        "lux": 400.0,
        "reliability": reliability,
        "source": source,
        "metadata": {},
        "measured_at": datetime.now(UTC) - timedelta(days=age_days),
    }


def _default_settings() -> Settings:
    return Settings(
        light_measurement_freshness_sensor_days=7,
        light_measurement_freshness_camera_days=14,
        light_measurement_freshness_manual_days=30,
        light_measurement_freshness_default_days=14,
        light_measurement_min_reliability="medium",
    )


async def test_eligible_light_context_survives_handle_action_and_reaches_synthesis() -> None:
    """A successful eligible lookup must be retained in assistant state and
    passed into answer synthesis as a contextual observation."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": True},
        light_measurement=_measurement(),
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cada cuánto riego mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )

    assert result.get("light_context_relevant") is True
    assert result.get("light_context") is not None
    assert result["light_context"]["source"] == "sensor"
    assert result["light_context"]["approximate"] is False
    grounded_prompt = tools.model_prompts[-1]
    assert "User-measured light context" in grounded_prompt
    assert "NOT species-level evidence" in grounded_prompt


async def test_recent_reliable_measurement_is_eligible() -> None:
    """A fresh, reliable reading belonging to the selected plant is eligible."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": True},
        light_measurement=_measurement(age_days=1, reliability="high", source="sensor"),
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cuánta agua necesita mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context") is not None


async def test_stale_measurement_is_excluded() -> None:
    """A reading older than its source freshness threshold is ineligible."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": True},
        light_measurement=_measurement(source="sensor", age_days=30),
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cuánta luz necesita mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context") is None


async def test_unreliable_measurement_is_excluded() -> None:
    """A reading below the minimum reliability threshold is ineligible."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": True},
        light_measurement=_measurement(reliability="low", source="sensor", age_days=1),
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cuánta luz necesita mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context") is None


async def test_absent_measurement_recommends_remeasurement_in_prompt() -> None:
    """When light context is relevant but no eligible measurement exists, the
    synthesis prompt explains the limitation and recommends a new reading."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": True},
        light_measurement=None,
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cuánta luz necesita mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context") is None
    assert "recommend obtaining a new light reading" in tools.model_prompts[-1]


async def test_foreign_plant_measurement_is_excluded() -> None:
    """A measurement associated with a different garden plant is not retained."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": True},
        light_measurement=_measurement(),
        light_measurement_foreign=True,
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cuánta luz necesita mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context") is None


async def test_irrelevant_request_skips_light_lookup() -> None:
    """A request where light cannot affect the answer must not trigger a lookup."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": False},
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cada cuánto riego mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context_relevant") is False
    assert tools.light_measurement_lookup_kwargs is None
    assert "User-measured light context" not in tools.model_prompts[-1]


async def test_non_english_and_paraphrased_relevance_reaches_semantic_path() -> None:
    """A paraphrased relevant request must reach the semantic light-context path
    via the classifier signal, without keyword matches in the assistant graph."""
    tools = FakeTools(
        classifier_data={
            "language": "es",
            "answer_language": "es",
            "intent": "plant_care_question",
            "topic": "watering",
            "required_aspects": ["watering_frequency_or_trigger"],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": True,
            "light_context_relevant": True,
        },
        light_measurement=_measurement(),
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Mi Pata necesita más o menos agua según dónde la pongo?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context_relevant") is True
    assert result.get("light_context") is not None
    assert "User-measured light context" in tools.model_prompts[-1]


async def test_camera_measurement_retains_approximate_designation() -> None:
    """A camera-derived measurement keeps its approximate flag and is not
    presented as precise."""
    tools = FakeTools(
        classifier_data={**WATERING_CLASSIFIER, "light_context_relevant": True},
        light_measurement=_measurement(source="camera", age_days=1, reliability="medium"),
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="¿Cuánta luz necesita mi Pata?",
        plant_hint="Pata",
        plant_binomial_name=CONFIRMED_BINOMIAL,
    )
    assert result.get("light_context") is not None
    assert result["light_context"]["source"] == "camera"
    assert result["light_context"]["approximate"] is True
    assert "Approximate reading (camera-derived)" in tools.model_prompts[-1]


async def test_reminder_suggestion_discloses_eligible_light_context() -> None:
    """A reminder suggestion includes eligible light context in its
    justification, disclosing source and reliability."""
    tools = FakeTools(
        classifier_data={
            "language": "es",
            "answer_language": "es",
            "intent": "reminder_request",
            "topic": "watering",
            "required_aspects": [],
            "plant_reference": "Pata",
            "confidence": 0.92,
            "needs_retrieval": False,
            "light_context_relevant": True,
            "reminder_action": "water",
            "reminder_recurrence": "weekly",
            "reminder_due_at": "2026-06-01T10:30",
            "reminder_suggestion_requested": True,
        },
        light_measurement=_measurement(),
    )
    result = await AssistantGraph(tools, settings=_default_settings()).run(
        user_id=uuid4(),
        message="Suggest a reminder for Pata on 2026-06-01 10:30 to water weekly",
        plant_hint="Pata",
    )
    assert result.get("requires_confirmation") is True
    justification = result["reminder_suggestion"]["suggestion_justification"]
    assert "Light context" in justification
    assert "Source: sensor" in justification
    assert "Reliability: high" in justification
