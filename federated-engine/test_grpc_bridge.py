# test_grpc_bridge.py
import unittest
from concurrent import futures
import grpc
import federation_pb2
import federation_pb2_grpc
from grpc_server import AggregatorServicer

class TestGRPCBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start a local test server
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

    def test_weight_submission_serialization(self):
        """Test that arrays stream correctly without precision loss."""
        test_weights = [0.123456, 0.987654, 3.14159]
        
        request = federation_pb2.WeightUpdate(
            client_id="TestNode",
            sample_count=100,
            weights=test_weights
        )
        
        response = self.stub.SubmitWeightUpdate(request)
        self.assertTrue(response.success)
        
        # Verify the server received and stored the exact payload
        stored_weights = self.servicer.client_weights[0]
        self.assertEqual(len(stored_weights), 3)
        
        for sent, received in zip(test_weights, stored_weights):
            self.assertAlmostEqual(sent, received, places=5)

if __name__ == '__main__':
    unittest.main(verbosity=2)
