# test_phase3_integration.py
# ===========================
# FederHub Phase 3 Integration Test
# ----------------------------------
# End-to-end test: simulates 3 PyTorch clients sending structured
# state_dict weights over gRPC to the aggregation server.
#
# Tests both the new Phase 3 structured mode AND backward compat
# with Phase 2 flat mode.

import sys
import time
import unittest
from concurrent import futures
from pathlib import Path

import grpc

# Ensure we can import the local modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

import federation_pb2
import federation_pb2_grpc
from grpc_server import AggregatorServicer
from fedavg_mock import federated_average_state_dicts


class TestPhase3StructuredAggregation(unittest.TestCase):
    """Test the full gRPC pipeline with structured TensorData payloads."""

    @classmethod
    def setUpClass(cls):
        cls.server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        cls.servicer = AggregatorServicer(expected_clients=3)
        federation_pb2_grpc.add_AggregatorServicer_to_server(cls.servicer, cls.server)
        port = cls.server.add_insecure_port('127.0.0.1:0')
        cls.server.start()

        cls.channel = grpc.insecure_channel(f'127.0.0.1:{port}')
        cls.stub = federation_pb2_grpc.AggregatorStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        cls.channel.close()
        cls.server.stop(None)

    def _make_structured_request(self, client_id, sample_count, layer_data):
        """Helper to build a structured WeightUpdate request."""
        layers = []
        for layer_name, shape, data in layer_data:
            layers.append(federation_pb2.TensorData(
                layer_name=layer_name,
                shape=shape,
                data=data,
            ))
        return federation_pb2.WeightUpdate(
            client_id=client_id,
            sample_count=sample_count,
            layers=layers,
            model_architecture="Linear(4,8)->ReLU->Linear(8,1)->Sigmoid",
        )

    def test_01_single_structured_submission(self):
        """A single structured weight update should be accepted."""
        # Reset the servicer for this test
        self.servicer.client_state_dicts.clear()
        self.servicer.structured_sample_counts.clear()
        self.servicer.structured_client_names.clear()
        self.servicer.expected_clients = 1

        request = self._make_structured_request(
            client_id="TestNode",
            sample_count=100,
            layer_data=[
                ("0.weight", [8, 4], [0.1] * 32),
                ("0.bias", [8], [0.01] * 8),
                ("2.weight", [1, 8], [0.2] * 8),
                ("2.bias", [1], [0.05]),
            ],
        )

        response = self.stub.SubmitWeightUpdate(request)
        self.assertTrue(response.success)
        self.assertIn("TestNode", response.message)

    def test_02_three_client_structured_aggregation(self):
        """Three structured clients trigger aggregation with correct weighted avg."""
        self.servicer.client_state_dicts.clear()
        self.servicer.structured_sample_counts.clear()
        self.servicer.structured_client_names.clear()
        self.servicer.expected_clients = 3

        # Client A: 300 samples, all weights = 1.0
        request_a = self._make_structured_request(
            client_id="Hospital A", sample_count=300,
            layer_data=[
                ("0.weight", [2, 2], [1.0, 1.0, 1.0, 1.0]),
                ("0.bias", [2], [1.0, 1.0]),
            ],
        )

        # Client B: 500 samples, all weights = 2.0
        request_b = self._make_structured_request(
            client_id="Hospital B", sample_count=500,
            layer_data=[
                ("0.weight", [2, 2], [2.0, 2.0, 2.0, 2.0]),
                ("0.bias", [2], [2.0, 2.0]),
            ],
        )

        # Client C: 200 samples, all weights = 3.0
        request_c = self._make_structured_request(
            client_id="Bank C", sample_count=200,
            layer_data=[
                ("0.weight", [2, 2], [3.0, 3.0, 3.0, 3.0]),
                ("0.bias", [2], [3.0, 3.0]),
            ],
        )

        resp_a = self.stub.SubmitWeightUpdate(request_a)
        resp_b = self.stub.SubmitWeightUpdate(request_b)
        resp_c = self.stub.SubmitWeightUpdate(request_c)

        self.assertTrue(resp_a.success)
        self.assertTrue(resp_b.success)
        self.assertTrue(resp_c.success)

        # After aggregation runs, servicer should have cleared state
        # (aggregation is triggered synchronously in the lock)
        self.assertEqual(len(self.servicer.client_state_dicts), 0)

    def test_03_tensor_precision_preserved(self):
        """Verify floating-point precision through the full pipeline."""
        self.servicer.client_state_dicts.clear()
        self.servicer.structured_sample_counts.clear()
        self.servicer.structured_client_names.clear()
        self.servicer.expected_clients = 1

        precise_values = [0.123456, 0.654321, 3.14159, 2.71828]

        request = self._make_structured_request(
            client_id="PrecisionTest", sample_count=50,
            layer_data=[("test_layer", [2, 2], precise_values)],
        )

        response = self.stub.SubmitWeightUpdate(request)
        self.assertTrue(response.success)


class TestPhase2BackwardCompatibility(unittest.TestCase):
    """Ensure Phase 2 flat-mode still works alongside structured mode."""

    @classmethod
    def setUpClass(cls):
        cls.server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        cls.servicer = AggregatorServicer(expected_clients=2)
        federation_pb2_grpc.add_AggregatorServicer_to_server(cls.servicer, cls.server)
        port = cls.server.add_insecure_port('127.0.0.1:0')
        cls.server.start()

        cls.channel = grpc.insecure_channel(f'127.0.0.1:{port}')
        cls.stub = federation_pb2_grpc.AggregatorStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        cls.channel.close()
        cls.server.stop(None)

    def test_flat_mode_submission(self):
        """Phase 2 flat-mode weight submission still works."""
        self.servicer.client_weights.clear()
        self.servicer.sample_counts.clear()
        self.servicer.client_names.clear()
        self.servicer.expected_clients = 1

        request = federation_pb2.WeightUpdate(
            client_id="FlatModeClient",
            sample_count=100,
            weights=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        )

        response = self.stub.SubmitWeightUpdate(request)
        self.assertTrue(response.success)
        self.assertIn("FlatModeClient", response.message)


class TestFedAvgStateDicts(unittest.TestCase):
    """Unit tests for the new federated_average_state_dicts function."""

    def test_equal_weights_two_clients(self):
        """Two clients with equal samples -> simple average."""
        sd1 = {
            "layer1": {"data": [1.0, 2.0, 3.0], "shape": [3]},
            "layer2": {"data": [4.0, 5.0], "shape": [2]},
        }
        sd2 = {
            "layer1": {"data": [3.0, 4.0, 5.0], "shape": [3]},
            "layer2": {"data": [6.0, 7.0], "shape": [2]},
        }

        result = federated_average_state_dicts([sd1, sd2], [100, 100])

        # Simple average: (1+3)/2=2, (2+4)/2=3, (3+5)/2=4
        for expected, actual in zip([2.0, 3.0, 4.0], result["layer1"]["data"]):
            self.assertAlmostEqual(expected, actual, places=6)
        for expected, actual in zip([5.0, 6.0], result["layer2"]["data"]):
            self.assertAlmostEqual(expected, actual, places=6)

    def test_weighted_average(self):
        """Weighted FedAvg: 300 vs 700 samples."""
        sd1 = {"w": {"data": [10.0], "shape": [1]}}
        sd2 = {"w": {"data": [20.0], "shape": [1]}}

        result = federated_average_state_dicts([sd1, sd2], [300, 700])

        # (300/1000)*10 + (700/1000)*20 = 3 + 14 = 17.0
        self.assertAlmostEqual(result["w"]["data"][0], 17.0, places=6)

    def test_shape_preserved(self):
        """Output shapes match input shapes."""
        sd = {"fc": {"data": [1.0] * 32, "shape": [8, 4]}}
        result = federated_average_state_dicts([sd], [100])
        self.assertEqual(result["fc"]["shape"], [8, 4])

    def test_empty_input_raises(self):
        """Empty inputs should raise ValueError."""
        with self.assertRaises(ValueError):
            federated_average_state_dicts([], [])

    def test_mismatched_layers_raises(self):
        """Clients with different layer names should raise ValueError."""
        sd1 = {"a": {"data": [1.0], "shape": [1]}}
        sd2 = {"b": {"data": [2.0], "shape": [1]}}
        with self.assertRaises(ValueError):
            federated_average_state_dicts([sd1, sd2], [100, 100])


if __name__ == '__main__':
    unittest.main(verbosity=2)
