"""La CLI V3 no reutiliza rutas V2 ni factura en modo preparación."""

from __future__ import annotations

import sys

import pytest

from scripts import run_groundtruth_campaign as campaign


def test_v3_default_paths_are_distinct(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "run_groundtruth_campaign", "--protocol", "v3",
        "--csv", "data/evaluation/ground_truth_547_v3.csv",
        "--task-id", "ET01-R1",
    ])
    args = campaign.parse_args()
    assert args.protocol == "v3"
    assert args.execute is False
    assert args.output.name == "v3_binary_campaign_runs.jsonl"
    assert args.context_cache.name == "v3_binary_legal_context_snapshots.jsonl"
    assert args.unit_checkpoints.name == "v3_binary_unit_checkpoints.jsonl"
    assert args.output != args.context_cache != args.unit_checkpoints


def test_v2_is_default_for_historical_scripts(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "run_groundtruth_campaign",
        "--csv", "data/evaluation/ground_truth_547.csv",
        "--task-id", "ET04-R1",
    ])
    args = campaign.parse_args()
    assert args.protocol == "v2"
    assert args.output.name == "v2_binary_campaign_runs.jsonl"


def test_v3_refuses_historical_data_file(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "run_groundtruth_campaign", "--protocol", "v3",
        "--csv", "data/evaluation/ground_truth_547.csv",
        "--task-id", "ET01-R1",
    ])
    with pytest.raises(SystemExit):
        campaign.parse_args()


def test_v3_refuses_v2_result_collision(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "run_groundtruth_campaign", "--protocol", "v3",
        "--csv", "data/evaluation/ground_truth_547_v3.csv",
        "--task-id", "ET01-R1",
        "--output", "data/evaluation/v2_binary_campaign_runs.jsonl",
    ])
    with pytest.raises(SystemExit):
        campaign.parse_args()


def test_paid_execution_requires_both_confirm_and_budget(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "run_groundtruth_campaign", "--protocol", "v3",
        "--csv", "data/evaluation/ground_truth_547_v3.csv",
        "--task-id", "ET01-R1", "--execute",
    ])
    with pytest.raises(SystemExit):
        campaign.parse_args()
