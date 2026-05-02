"""Tests for client/ml/train.py helpers.

We exercise the helper functions individually rather than running the
``main()`` entry point.  This keeps each test fast, deterministic, and
independent of CLI parsing.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import torch
from torch import nn
from torch.utils.data import TensorDataset

import train


class TestResolveDatasetPath:
    def test_returns_csv_path_when_provided(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("col\n1\n", encoding="utf-8")
        result = train.resolve_dataset_path(None, path)
        assert result == path.resolve()

    def test_csv_path_takes_precedence_over_input_dir(self, tmp_path):
        explicit = tmp_path / "explicit.csv"
        explicit.write_text("c\n1\n", encoding="utf-8")
        (tmp_path / "other.csv").write_text("c\n1\n", encoding="utf-8")
        result = train.resolve_dataset_path(tmp_path, explicit)
        assert result == explicit.resolve()

    def test_finds_first_csv_alphabetically_in_input_dir(self, tmp_path):
        (tmp_path / "z.csv").write_text("c\n1\n", encoding="utf-8")
        (tmp_path / "a.csv").write_text("c\n1\n", encoding="utf-8")
        (tmp_path / "m.csv").write_text("c\n1\n", encoding="utf-8")
        result = train.resolve_dataset_path(tmp_path, None)
        assert result.name == "a.csv"

    def test_raises_when_neither_path_provided(self):
        with pytest.raises(ValueError, match="Provide either"):
            train.resolve_dataset_path(None, None)

    def test_raises_when_input_dir_has_no_csv(self, tmp_path):
        (tmp_path / "x.txt").write_text("not a csv", encoding="utf-8")
        with pytest.raises(ValueError, match="No CSV files"):
            train.resolve_dataset_path(tmp_path, None)


class TestLoadCheckpointMetadata:
    def test_returns_defaults_when_path_is_none(self):
        result = train.load_checkpoint_metadata(None)
        assert result["input_columns"] == train.DEFAULT_INPUT_COLUMNS
        assert result["label_column"] == train.DEFAULT_LABEL_COLUMN

    def test_reads_metadata_from_dict_checkpoint(self, tmp_path):
        ckpt_path = tmp_path / "ckpt.pt"
        torch.save(
            {
                "input_columns": ["age", "income", "credit_score"],
                "label_column": "default",
                "state_dict": {},
            },
            ckpt_path,
        )
        result = train.load_checkpoint_metadata(ckpt_path)
        assert result["input_columns"] == ["age", "income", "credit_score"]
        assert result["label_column"] == "default"

    def test_falls_back_to_defaults_when_metadata_absent(self, tmp_path, synthetic_state_dict):
        ckpt_path = tmp_path / "ckpt.pt"
        torch.save(synthetic_state_dict, ckpt_path)
        result = train.load_checkpoint_metadata(ckpt_path)
        assert result["input_columns"] == train.DEFAULT_INPUT_COLUMNS
        assert result["label_column"] == train.DEFAULT_LABEL_COLUMN

    def test_accepts_feature_columns_alias(self, tmp_path):
        ckpt_path = tmp_path / "ckpt.pt"
        torch.save({"feature_columns": ["a", "b"]}, ckpt_path)
        result = train.load_checkpoint_metadata(ckpt_path)
        assert result["input_columns"] == ["a", "b"]


class TestLoadDataset:
    def test_loads_csv_into_tensor_dataset(self, synthetic_csv):
        path = synthetic_csv()
        dataset = train.load_dataset(
            path,
            ["feature_1", "feature_2", "feature_3", "feature_4"],
            "label",
        )
        assert isinstance(dataset, TensorDataset)
        assert len(dataset) == 4

    def test_features_have_correct_shape_and_dtype(self, synthetic_csv):
        path = synthetic_csv()
        dataset = train.load_dataset(
            path,
            ["feature_1", "feature_2", "feature_3", "feature_4"],
            "label",
        )
        x, y = dataset.tensors
        assert x.shape == (4, 4)
        assert y.shape == (4, 1)
        assert x.dtype == torch.float32
        assert y.dtype == torch.float32

    def test_raises_on_missing_columns(self, synthetic_csv):
        path = synthetic_csv(columns=["a", "b", "label"], rows=[[1, 2, 0]])
        with pytest.raises(ValueError, match="missing required columns"):
            train.load_dataset(path, ["x", "y"], "label")

    def test_raises_on_empty_csv(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text(
            "feature_1,feature_2,feature_3,feature_4,label\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="empty"):
            train.load_dataset(
                path,
                ["feature_1", "feature_2", "feature_3", "feature_4"],
                "label",
            )


class TestCreateModel:
    def test_returns_correct_architecture(self):
        model = train.create_model(input_size=4)
        assert isinstance(model, nn.Sequential)
        assert len(model) == 4
        assert isinstance(model[0], nn.Linear)
        assert model[0].in_features == 4
        assert model[0].out_features == 8
        assert isinstance(model[1], nn.ReLU)
        assert isinstance(model[2], nn.Linear)
        assert model[2].in_features == 8
        assert model[2].out_features == 1
        assert isinstance(model[3], nn.Sigmoid)

    @pytest.mark.parametrize("input_size", [1, 4, 10, 64])
    def test_handles_different_input_sizes(self, input_size):
        model = train.create_model(input_size=input_size)
        assert model[0].in_features == input_size

    def test_forward_pass_produces_sigmoid_output(self):
        model = train.create_model(input_size=4)
        x = torch.randn(3, 4)
        y = model(x)
        assert y.shape == (3, 1)
        assert (y >= 0).all() and (y <= 1).all()


class TestLoadCheckpointIfPresent:
    def test_no_checkpoint_keeps_random_init(self, capsys):
        model = train.create_model(input_size=4)
        original = model[0].weight.clone()
        train.load_checkpoint_if_present(model, None)
        assert torch.equal(model[0].weight, original)
        out = capsys.readouterr().out
        assert "fresh model" in out

    def test_loads_state_dict_from_checkpoint(self, tmp_path):
        donor = train.create_model(input_size=4)
        ckpt_path = tmp_path / "ckpt.pt"
        torch.save(donor.state_dict(), ckpt_path)

        recipient = train.create_model(input_size=4)
        train.load_checkpoint_if_present(recipient, ckpt_path)
        assert torch.equal(recipient[0].weight, donor[0].weight)

    def test_loads_wrapped_state_dict(self, tmp_path):
        donor = train.create_model(input_size=4)
        ckpt_path = tmp_path / "ckpt.pt"
        torch.save({"state_dict": donor.state_dict()}, ckpt_path)

        recipient = train.create_model(input_size=4)
        train.load_checkpoint_if_present(recipient, ckpt_path)
        assert torch.equal(recipient[0].weight, donor[0].weight)

    def test_raises_on_incompatible_checkpoint(self, tmp_path):
        wrong = nn.Linear(99, 99)
        ckpt_path = tmp_path / "wrong.pt"
        torch.save(wrong.state_dict(), ckpt_path)

        recipient = train.create_model(input_size=4)
        with pytest.raises(ValueError, match="not be loaded"):
            train.load_checkpoint_if_present(recipient, ckpt_path)


class TestBuildOutputCheckpointPath:
    def test_default_name_when_no_checkpoint(self, tmp_path):
        result = train.build_output_checkpoint_path(tmp_path, None)
        assert result.name == "updated_model.pt"
        assert result.parent == tmp_path

    def test_prefixed_name_when_checkpoint_provided(self, tmp_path):
        ckpt = Path("/somewhere/fracture_model.pt")
        result = train.build_output_checkpoint_path(tmp_path, ckpt)
        assert result.name == "updated_fracture_model.pt"
        assert result.parent == tmp_path


class TestTrainModel:
    def _bigger_dataset(self, synthetic_csv):
        rows = [
            [float(i), float(i + 1), float(i + 2), float(i + 3), float(i % 2)]
            for i in range(20)
        ]
        path = synthetic_csv(rows=rows)
        return train.load_dataset(
            path,
            ["feature_1", "feature_2", "feature_3", "feature_4"],
            "label",
        )

    def test_returns_model_with_correct_architecture(self, synthetic_csv):
        dataset = self._bigger_dataset(synthetic_csv)
        model = train.train_model(dataset, epochs=1, checkpoint_path=None, input_size=4)
        assert isinstance(model, nn.Sequential)
        assert len(model) == 4
        assert model[0].in_features == 4

    def test_weights_actually_change_after_training(self, synthetic_csv):
        dataset = self._bigger_dataset(synthetic_csv)
        torch.manual_seed(0)
        baseline = train.create_model(input_size=4)
        baseline_weight = baseline[0].weight.clone()

        torch.manual_seed(0)
        trained = train.train_model(
            dataset, epochs=2, checkpoint_path=None, input_size=4
        )
        assert not torch.equal(trained[0].weight, baseline_weight)

    def test_resumes_from_checkpoint(self, tmp_path, synthetic_csv):
        donor = train.create_model(input_size=4)
        ckpt_path = tmp_path / "ckpt.pt"
        torch.save(donor.state_dict(), ckpt_path)

        dataset = self._bigger_dataset(synthetic_csv)
        model = train.train_model(
            dataset, epochs=1, checkpoint_path=ckpt_path, input_size=4
        )
        assert isinstance(model, nn.Sequential)


class TestFlushSensitiveTensors:
    def test_zeros_out_tensors(self):
        a = torch.tensor([1.0, 2.0, 3.0])
        b = torch.tensor([[4.0, 5.0], [6.0, 7.0]])
        train.flush_sensitive_tensors(a, b)
        assert torch.equal(a, torch.zeros_like(a))
        assert torch.equal(b, torch.zeros_like(b))

    def test_skips_none_values(self):
        a = torch.tensor([1.0, 2.0])
        train.flush_sensitive_tensors(a, None, None)
        assert torch.equal(a, torch.zeros_like(a))

    def test_handles_no_args(self):
        train.flush_sensitive_tensors()
