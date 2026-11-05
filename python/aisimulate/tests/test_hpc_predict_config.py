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
