"""MalleServe prediction configuration and strict top-level section handling."""
import pytest
from pydantic import ValidationError

from aisimulate.config.cli import HpcPredictionConfig
from aisimulate.config.common import split_config_sections


def test_hpc_is_predict_core_section() -> None:
    hpc = {
        "availability_trace": "traces/hpc_availability.jsonl",
        "reclamation": "immediate",
        "recovery": "full_request_restart",
        "max_restarts": 2,
    }
    core, adapters = split_config_sections(
        {"engine": {"mode": "aggregated"}, "hpc": hpc, "router": {"policy": "round_robin"}},
        command="predict",
    )
    assert core["hpc"] == hpc
    assert adapters == {"router": {"policy": "round_robin"}}


def test_hpc_restart_requires_immediate_reclamation() -> None:
    with pytest.raises(ValidationError, match="immediate reclamation"):
        HpcPredictionConfig(
            availability_trace="trace.jsonl",
            reclamation="ignored",
            recovery="full_request_restart",
            max_restarts=2,
        )


def test_hpc_restart_requires_budget() -> None:
    with pytest.raises(ValidationError, match="positive max_restarts"):
        HpcPredictionConfig(
            availability_trace="trace.jsonl",
            recovery="full_request_restart",
        )


def test_hpc_defaults_to_immediate_no_recovery() -> None:
    config = HpcPredictionConfig(availability_trace="trace.jsonl")
    assert config.reclamation == "immediate"
    assert config.recovery == "none"
    assert config.max_restarts == 0


@pytest.mark.parametrize(
    ("scenario", "extra_workers", "trace"),
    [
        ("persistent_only", 0, None),
        ("ideal_elasticity", 4, None),
        ("perfect_transient", 0, "trace.jsonl"),
        ("realistic_transient", 0, "trace.jsonl"),
    ],
)
def test_named_capacity_scenarios(scenario: str, extra_workers: int, trace: str | None) -> None:
    config = HpcPredictionConfig(
        scenario=scenario, extra_workers=extra_workers, availability_trace=trace
    )
    assert config.scenario == scenario


def test_ideal_elasticity_requires_extra_capacity() -> None:
    with pytest.raises(ValidationError, match="extra_workers"):
        HpcPredictionConfig(scenario="ideal_elasticity")


def test_perfect_transient_requires_trace_and_disallows_restart() -> None:
    with pytest.raises(ValidationError, match="availability_trace"):
        HpcPredictionConfig(scenario="perfect_transient")
    with pytest.raises(ValidationError, match="graceful oracle"):
        HpcPredictionConfig(
            scenario="perfect_transient", availability_trace="trace.jsonl",
            recovery="full_request_restart", max_restarts=2,
        )
