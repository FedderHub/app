import argparse
# Phase 3: Updated to support structured PyTorch state_dict payloads
# while maintaining backward compatibility with Phase 2 flat-array mode.
# Also integrates with Alpha's PostgreSQL to record per-round metrics.
import json
import os
import grpc
from concurrent import futures
import threading
from dotenv import load_dotenv

import federation_pb2
import federation_pb2_grpc
from fedavg_mock import federated_average, federated_average_state_dicts

# Optional DB integration — gracefully degrades if DB is unavailable
try:
    from db_connector import (
        create_db_session,
        fetch_job_config,
        record_round_metric,
        update_job_status,
    )
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

load_dotenv()


class AggregatorServicer(federation_pb2_grpc.AggregatorServicer):
    def __init__(self, expected_clients: int = 3, job_id: int = None, db_url: str = None):
        self.expected_clients = expected_clients
        self.job_id = job_id
        self.current_round = 0
        # Phase 2 flat mode storage
        self.client_weights = []
        self.sample_counts = []
        self.client_names = []
        # Phase 3 structured mode storage
        self.client_state_dicts = []
        self.structured_sample_counts = []
        self.structured_client_names = []
        self.lock = threading.Lock()
        self.configured_round_count = None
        # DB session (optional)
        self.db_session = None
        if DB_AVAILABLE and db_url:
            try:
                self.db_session, _ = create_db_session(db_url)
                print(f"[SERVER] Connected to database for job_id={job_id}")
                if job_id:
                    config = fetch_job_config(self.db_session, job_id)
                    self.configured_round_count = config.get("round_count")
                    update_job_status(self.db_session, job_id, "running")
                    print(
                        "[SERVER] Loaded job config: "
                        f"rounds={config.get('round_count')}, "
                        f"local_epochs={config.get('local_epochs')}"
                    )
            except Exception as e:
                print(f"[SERVER WARNING] DB connection failed: {e}. Metrics will not be recorded.")

    def SubmitWeightUpdate(self, request, context):
        with self.lock:
            # Detect mode: if layers are present, use structured mode
            if len(request.layers) > 0:
                return self._handle_structured(request)
            else:
                return self._handle_flat(request)

    def _handle_flat(self, request):
        """Phase 2 backward-compatible flat-array mode."""
        self.client_names.append(request.client_id)
        self.sample_counts.append(request.sample_count)
        self.client_weights.append(list(request.weights))

        print(f"[SERVER] Received FLAT update from {request.client_id} "
              f"({request.sample_count} samples, {len(request.weights)} parameters).")

        if len(self.client_weights) == self.expected_clients:
            self._run_flat_aggregation()

        return federation_pb2.UpdateAck(
            success=True,
            message=f"Update received from {request.client_id} successfully."
        )

    def _handle_structured(self, request):
        """Phase 3 structured state_dict mode for real PyTorch models."""
        state_dict = {}
        total_params = 0
        for tensor in request.layers:
            state_dict[tensor.layer_name] = {
                "data": list(tensor.data),
                "shape": list(tensor.shape),
            }
            total_params += len(tensor.data)

        self.structured_client_names.append(request.client_id)
        self.structured_sample_counts.append(request.sample_count)
        self.client_state_dicts.append(state_dict)

        layer_names = [t.layer_name for t in request.layers]
        print(f"[SERVER] Received STRUCTURED update from {request.client_id} "
              f"({request.sample_count} samples, {total_params} parameters "
              f"across {len(request.layers)} layers: {layer_names}).")

        if len(request.model_architecture):
            print(f"[SERVER]   Model architecture: {request.model_architecture}")

        if len(self.client_state_dicts) == self.expected_clients:
            self._run_structured_aggregation()

        return federation_pb2.UpdateAck(
            success=True,
            message=f"Structured update received from {request.client_id} successfully."
        )

    def _run_flat_aggregation(self):
        """Phase 2 flat-mode aggregation."""
        print("\n[SERVER] Target client count reached. Starting FedAvg aggregation (flat mode)...")
        try:
            global_weights = federated_average(self.client_weights, self.sample_counts)
            print("[SERVER] Aggregation Successful! New Global Weights:")
            print([f"{w:.6f}" for w in global_weights])

            self.client_weights.clear()
            self.sample_counts.clear()
            self.client_names.clear()
        except Exception as e:
            print(f"[SERVER ERROR] Aggregation failed: {e}")

    def _run_structured_aggregation(self):
        """Phase 3 structured per-layer aggregation."""
        print("\n[SERVER] Target client count reached. Starting FedAvg aggregation (structured mode)...")
        try:
            global_state_dict = federated_average_state_dicts(
                self.client_state_dicts,
                self.structured_sample_counts,
            )

            total_params = sum(len(v["data"]) for v in global_state_dict.values())
            n_total = sum(self.structured_sample_counts)

            print(f"[SERVER] Aggregation Successful! Global model: "
                  f"{len(global_state_dict)} layers, {total_params} parameters.")
            print(f"[SERVER] Total samples used: {n_total}")
            print("[SERVER] Weight contributions:")
            for name, n_k in zip(self.structured_client_names, self.structured_sample_counts):
                pct = (n_k / n_total) * 100
                print(f"  {name:<15} -> {pct:.1f}% influence")

            print("[SERVER] Aggregated layers:")
            for layer_name, layer_info in global_state_dict.items():
                preview = [f"{v:.6f}" for v in layer_info["data"][:4]]
                suffix = "..." if len(layer_info["data"]) > 4 else ""
                print(f"  {layer_name} {layer_info['shape']}: [{', '.join(preview)}{suffix}]")

            print("\n[SERVER] Global model ready for distribution.")

            # --- Record metrics to Alpha's DB ---
            self.current_round += 1
            self._record_metrics_to_db(
                num_clients=len(self.structured_client_names),
                total_samples=n_total,
                global_weights_snapshot={
                    layer: {
                        "shape": info["shape"],
                        "mean": sum(info["data"]) / max(len(info["data"]), 1),
                        "num_params": len(info["data"]),
                    }
                    for layer, info in global_state_dict.items()
                },
            )

            if (
                self.db_session
                and self.job_id
                and self.configured_round_count
                and self.current_round >= self.configured_round_count
            ):
                update_job_status(self.db_session, self.job_id, "completed")
                print(f"[SERVER] Job {self.job_id} marked completed.")

            # Reset state for the next round
            self.client_state_dicts.clear()
            self.structured_sample_counts.clear()
            self.structured_client_names.clear()
        except Exception as e:
            print(f"[SERVER ERROR] Structured aggregation failed: {e}")

    def _record_metrics_to_db(self, num_clients=None, total_samples=None,
                               accuracy=None, loss=None, global_weights_snapshot=None):
        """Write round metrics to Alpha's PostgreSQL (if DB is connected)."""
        if not self.db_session or not self.job_id:
            return

        try:
            metric = record_round_metric(
                session=self.db_session,
                job_id=self.job_id,
                round_number=self.current_round,
                accuracy=accuracy,
                loss=loss,
                num_clients=num_clients,
                total_samples=total_samples,
                global_weights_snapshot=global_weights_snapshot,
            )
            print(f"[SERVER] Round {self.current_round} metrics recorded to DB (metric_id={metric.id})")
        except Exception as e:
            print(f"[SERVER WARNING] Failed to record metrics: {e}")


def serve(expected_clients: int = 3, job_id: int = None, db_url: str = None, port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    federation_pb2_grpc.add_AggregatorServicer_to_server(
        AggregatorServicer(
            expected_clients=expected_clients,
            job_id=job_id,
            db_url=db_url,
        ),
        server,
    )
    server.add_insecure_port(f'[::]:{port}')
    print(f"[SERVER] gRPC Aggregator listening on port {port}...")
    print(f"[SERVER] Expected clients per round: {expected_clients}")
    if job_id:
        print(f"[SERVER] Recording aggregation metrics for job_id={job_id}")
    print("[SERVER] Supports: flat mode (Phase 2) + structured mode (Phase 3)")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="FederHub Gamma gRPC aggregation server")
    parser.add_argument("--expected-clients", type=int, default=int(os.getenv("EXPECTED_CLIENTS", "3")))
    parser.add_argument("--job-id", type=int, default=int(os.getenv("JOB_ID", "0")))
    parser.add_argument("--port", type=int, default=int(os.getenv("GRPC_PORT", "50051")))
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()

    serve(
        expected_clients=args.expected_clients,
        job_id=args.job_id or None,
        db_url=args.db_url or None,
        port=args.port,
    )
