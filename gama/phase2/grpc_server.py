# grpc_server.py
import grpc
from concurrent import futures
import threading

import federation_pb2
import federation_pb2_grpc
from fedavg_mock import federated_average

class AggregatorServicer(federation_pb2_grpc.AggregatorServicer):
    def __init__(self, expected_clients: int = 3):
        self.expected_clients = expected_clients
        self.client_weights = []
        self.sample_counts = []
        self.client_names = []
        self.lock = threading.Lock()

    def SubmitWeightUpdate(self, request, context):
        with self.lock:
            # Store the incoming data
            self.client_names.append(request.client_id)
            self.sample_counts.append(request.sample_count)
            self.client_weights.append(list(request.weights))
            
            print(f"[SERVER] Received update from {request.client_id} "
                  f"({request.sample_count} samples, {len(request.weights)} parameters).")

            # Trigger aggregation if we hit the expected client count
            if len(self.client_weights) == self.expected_clients:
                self._run_aggregation()

            return federation_pb2.UpdateAck(
                success=True, 
                message=f"Update received from {request.client_id} successfully."
            )

    def _run_aggregation(self):
        print("\n[SERVER] Target client count reached. Starting FedAvg aggregation...")
        try:
            global_weights = federated_average(self.client_weights, self.sample_counts)
            print("[SERVER] Aggregation Successful! New Global Weights:")
            print([f"{w:.6f}" for w in global_weights])
            
            # Reset state for the next round
            self.client_weights.clear()
            self.sample_counts.clear()
            self.client_names.clear()
        except Exception as e:
            print(f"[SERVER ERROR] Aggregation failed: {e}")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    federation_pb2_grpc.add_AggregatorServicer_to_server(AggregatorServicer(), server)
    server.add_insecure_port('[::]:50051')
    print("[SERVER] gRPC Aggregator listening on port 50051...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()