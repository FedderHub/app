"""Tests for client/ml/inspect_checkpoint.py.

The script is invoked from Electron via the desktop client and prints a
single JSON document to stdout.  We call its ``main()`` directly with a
patched ``sys.argv`` and capture stdout to inspect the result.
"""
from __future__ import annotations

import json
import sys

import pytest
import torch
from torch import nn

import inspect_checkpoint


def _run_main(monkeypatch, capsys, argv):
    """Run ``inspect_checkpoint.main()`` with the given argv; return parsed JSON."""
    monkeypatch.setattr(sys, "argv", argv)
    inspect_checkpoint.main()
    return json.loads(capsys.readouterr().out)


class TestNoArgs:
    def test_returns_not_ok_with_default_columns_in_summary(self, monkeypatch, capsys):
        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py"])
        assert result["ok"] is False
        assert result["columns"] == []
        assert "feature_1, feature_2, feature_3, feature_4, label" in result["summary"]


class TestMetadataAwareCheckpoint:
    def test_returns_ok_with_metadata_columns(self, monkeypatch, capsys, tmp_path):
        ckpt = tmp_path / "ckpt.pt"
        torch.save(
            {
                "input_columns": ["age", "income"],
                "label_column": "default",
                "state_dict": {},
            },
            ckpt,
        )
        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py", str(ckpt)])
        assert result["ok"] is True
        assert result["columns"] == ["age", "income", "default"]
        assert "Checkpoint metadata found" in result["summary"]

    def test_uses_default_label_when_label_column_missing(self, monkeypatch, capsys, tmp_path):
        ckpt = tmp_path / "ckpt.pt"
        torch.save({"input_columns": ["x", "y"]}, ckpt)
        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py", str(ckpt)])
        assert result["ok"] is True
        assert result["columns"] == ["x", "y", "label"]

    def test_accepts_feature_columns_alias(self, monkeypatch, capsys, tmp_path):
        ckpt = tmp_path / "ckpt.pt"
        torch.save({"feature_columns": ["a", "b", "c"]}, ckpt)
        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py", str(ckpt)])
        assert result["ok"] is True
        assert result["columns"] == ["a", "b", "c", "label"]


class TestStateDictOnlyCheckpoint:
    def test_infers_columns_from_first_linear_layer(self, monkeypatch, capsys, tmp_path):
        model = nn.Sequential(
            nn.Linear(6, 8),
            nn.ReLU(),
            nn.Linear(8, 1),
        )
        ckpt = tmp_path / "ckpt.pt"
        torch.save(model.state_dict(), ckpt)

        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py", str(ckpt)])
        assert result["ok"] is True
        expected = [f"feature_{i}" for i in range(1, 7)] + ["label"]
        assert result["columns"] == expected
        assert "6 numeric input features" in result["summary"]

    def test_infers_four_features_for_default_arch(self, monkeypatch, capsys, tmp_path):
        model = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Linear(8, 1))
        ckpt = tmp_path / "ckpt.pt"
        torch.save(model.state_dict(), ckpt)

        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py", str(ckpt)])
        assert result["ok"] is True
        assert result["columns"] == ["feature_1", "feature_2", "feature_3", "feature_4", "label"]


class TestCorruptCheckpoint:
    def test_returns_not_ok_when_file_is_garbage(self, monkeypatch, capsys, tmp_path):
        bad = tmp_path / "corrupt.pt"
        bad.write_bytes(b"not a real torch checkpoint payload at all")
        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py", str(bad)])
        assert result["ok"] is False
        assert result["columns"] == []

    def test_returns_not_ok_when_file_does_not_exist(self, monkeypatch, capsys, tmp_path):
        ghost = tmp_path / "ghost.pt"
        result = _run_main(monkeypatch, capsys, ["inspect_checkpoint.py", str(ghost)])
        assert result["ok"] is False
