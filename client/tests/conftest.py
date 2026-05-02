"""Shared fixtures for Team Beta (client/) tests.

Adds the client/ and client/ml/ directories to sys.path so that the test
modules can import ``train``, ``inspect_checkpoint``, and ``grpc_weight_sender``
directly without needing __init__.py files in the production code.

The federated-engine/ directory is also added so that federation_pb2
imports work directly in tests (not just lazily through grpc_weight_sender).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

# Make production modules importable without touching the source tree
CLIENT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = CLIENT_ROOT.parent
sys.path.insert(0, str(CLIENT_ROOT))
sys.path.insert(0, str(CLIENT_ROOT / "ml"))
sys.path.insert(0, str(REPO_ROOT / "federated-engine"))


@pytest.fixture
def synthetic_csv(tmp_path):
    """Factory: create a CSV with given columns and rows, return its path."""
    def _make(name="data.csv", columns=None, rows=None):
        columns = columns or ["feature_1", "feature_2", "feature_3", "feature_4", "label"]
        rows = rows or [
            [1.0, 2.0, 3.0, 4.0, 1.0],
            [0.5, 1.5, 2.5, 3.5, 0.0],
            [2.0, 3.0, 4.0, 5.0, 1.0],
            [0.1, 0.2, 0.3, 0.4, 0.0],
        ]
        path = tmp_path / name
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                writer.writerow(row)
        return path

    return _make


@pytest.fixture
def synthetic_state_dict():
    """A small state_dict matching train.py's model architecture."""
    import torch
    from torch import nn

    model = nn.Sequential(
        nn.Linear(4, 8),
        nn.ReLU(),
        nn.Linear(8, 1),
        nn.Sigmoid(),
    )
    return model.state_dict()
