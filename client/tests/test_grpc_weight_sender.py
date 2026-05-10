"""Tests for client/grpc_weight_sender.py.

We start a real local gRPC server with a recording servicer for each test
that needs network roundtrips.  This is more honest than mocking because
it exercises actual protobuf serialization, which is the entire point of
this module.
"""
from __future__ import annotations

import csv
import json
from concurrent import futures

import grpc
import pytest
import torch
from torch import nn

import federation_pb2
import federation_pb2_grpc
import grpc_weight_sender


class TestLoadStateDict:
    def test_loads_raw_state_dict(self, tmp_path):
        model = nn.Linear(4, 1)
        ckpt = tmp_path / "raw.pt"
        torch.save(model.state_dict(), ckpt)

        result = grpc_weight_sender.load_state_dict(str(ckpt))
        assert "weight" in result
        assert "bias" in result

    def test_loads_wrapped_state_dict(self, tmp_path):
        model = nn.Linear(4, 1)
        ckpt = tmp_path / "wrapped.pt"
        torch.save({"state_dict": model.state_dict()}, ckpt)

        result = grpc_weight_sender.load_state_dict(str(ckpt))
        assert "weight" in result
        assert "bias" in result


class TestGetSampleCount:
    def test_returns_default_when_summary_path_missing(self, tmp_path):
        nonexistent = str(tmp_path / "missing.json")
        assert grpc_weight_sender.get_sample_count(nonexistent) == 100

    def test_returns_default_when_path_empty(self):
        assert grpc_weight_sender.get_sample_count("") == 100

    def test_counts_csv_rows_minus_header(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["a", "b"])
            for i in range(50):
                writer.writerow([i, i * 2])

        summary = tmp_path / "run_summary.json"
        summary.write_text(json.dumps({"dataset": str(csv_path)}), encoding="utf-8")

        assert grpc_weight_sender.get_sample_count(str(summary)) == 50

    def test_returns_default_when_summary_lacks_dataset(self, tmp_path):
        summary = tmp_path / "summary.json"
        summary.write_text(json.dumps({"epochs": 8}), encoding="utf-8")
        assert grpc_weight_sender.get_sample_count(str(summary)) == 100

    def test_returns_default_when_dataset_path_missing(self, tmp_path):
        summary = tmp_path / "summary.json"
        summary.write_text(
            json.dumps({"dataset": "/this/does/not/exist.csv"}),
            encoding="utf-8",
        )
        assert grpc_weight_sender.get_sample_count(str(summary)) == 100


class TestStateDictToProto:
    def test_creates_one_proto_per_layer(self):
        model = nn.Linear(4, 2)
        layers = grpc_weight_sender.state_dict_to_proto_layers(model.state_dict())
        names = {layer.layer_name for layer in layers}
        assert names == {"weight", "bias"}

    def test_preserves_shape(self):
        model = nn.Linear(3, 2)
        layers = grpc_weight_sender.state_dict_to_proto_layers(model.state_dict())
        weight_layer = next(l for l in layers if l.layer_name == "weight")
        assert list(weight_layer.shape) == [2, 3]
        assert len(weight_layer.data) == 6

    def test_data_matches_flattened_tensor(self):
        sd = {"layer1": torch.tensor([[1.0, 2.0], [3.0, 4.0]])}
        layers = grpc_weight_sender.state_dict_to_proto_layers(sd)
        assert len(layers) == 1
        assert list(layers[0].shape) == [2, 2]
        assert list(layers[0].data) == pytest.approx([1.0, 2.0, 3.0, 4.0])

    def test_handles_multi_layer_model(self):
        model = nn.Sequential(nn.Linear(4, 8), nn.Linear(8, 1))
        layers = grpc_weight_sender.state_dict_to_proto_layers(model.state_dict())
        assert len(layers) == 4


class TestDescribeModel:
    def test_includes_layer_names_and_shapes(self):
        model = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Linear(8, 1), nn.Sigmoid())
        desc = grpc_weight_sender.describe_model(model.state_dict())
        assert "0.weight" in desc
        assert "[8, 4]" in desc
        assert "2.weight" in desc
        assert "[1, 8]" in desc
        assert "|" in desc


class _RecordingServicer(federation_pb2_grpc.AggregatorServicer):
    """Test gRPC service that records the request it received."""

    def __init__(self, return_success: bool = True):
        self.return_success = return_success
        self.received_request = None

    def SubmitWeightUpdate(self, request, context):
        self.received_request = request
        return federation_pb2.UpdateAck(
            success=self.return_success,
            message="recorded",
        )


@pytest.fixture
def grpc_server():
    """Start a local gRPC server with a recording servicer.  Yields (servicer, address)."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    servicer = _RecordingServicer()
    federation_pb2_grpc.add_AggregatorServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield servicer, f"127.0.0.1:{port}"
    finally:
        server.stop(None)


class TestSendWeights:
    def test_sends_request_and_returns_true(self, tmp_path, grpc_server):
        servicer, address = grpc_server

        model = nn.Sequential(nn.Linear(4, 8), nn.Linear(8, 1))
        ckpt = tmp_path / "model.pt"
        torch.save(model.state_dict(), ckpt)

        ok = grpc_weight_sender.send_weights(
            pt_path=str(ckpt),
            summary_path="",
            server_address=address,
            client_id="Hospital A",
        )
        assert ok is True

        assert servicer.received_request is not None
        assert servicer.received_request.client_id == "Hospital A"
        assert len(servicer.received_request.layers) == 4
        assert servicer.received_request.sample_count == 100
        assert servicer.received_request.model_architecture

    def test_returns_false_when_server_unreachable(self, tmp_path):
        model = nn.Linear(4, 1)
        ckpt = tmp_path / "model.pt"
        torch.save(model.state_dict(), ckpt)

        ok = grpc_weight_sender.send_weights(
            pt_path=str(ckpt),
            summary_path="",
            server_address="127.0.0.1:1",
            client_id="Test",
        )
        assert ok is False

    def test_uses_sample_count_from_summary_csv(self, tmp_path, grpc_server):
        servicer, address = grpc_server

        csv_path = tmp_path / "data.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["a", "b"])
            for i in range(25):
                writer.writerow([i, i])

        summary = tmp_path / "run_summary.json"
        summary.write_text(json.dumps({"dataset": str(csv_path)}), encoding="utf-8")

        model = nn.Linear(4, 1)
        ckpt = tmp_path / "model.pt"
        torch.save(model.state_dict(), ckpt)

        ok = grpc_weight_sender.send_weights(
            pt_path=str(ckpt),
            summary_path=str(summary),
            server_address=address,
            client_id="Hospital B",
        )
        assert ok is True
        assert servicer.received_request.sample_count == 25

    def test_propagates_server_failure(self, tmp_path):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        servicer = _RecordingServicer(return_success=False)
        federation_pb2_grpc.add_AggregatorServicer_to_server(servicer, server)
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        try:
            model = nn.Linear(4, 1)
            ckpt = tmp_path / "model.pt"
            torch.save(model.state_dict(), ckpt)

            ok = grpc_weight_sender.send_weights(
                pt_path=str(ckpt),
                summary_path="",
                server_address=f"127.0.0.1:{port}",
                client_id="Failing",
            )
            assert ok is False
        finally:
            server.stop(None)
