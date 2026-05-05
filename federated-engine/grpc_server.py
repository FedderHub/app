import argparse
import json
import os
import grpc
from concurrent import futures
import threading
from dotenv import load_dotenv

import federation_pb2
import federation_pb2_grpc
from fedavg_mock import federated_average, federated_average_state_dicts

# Optional DB integration
try:
    from db_connector import (
        create_db_session,
        fetch_job_config,
        record_round_metric,
        update_job_status,
        record_client_submission
    )
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

load_dotenv()


class AggregatorServicer(federation_pb2_grpc.AggregatorServicer):
    def __init__(self, db_url: str = None):
        self.lock = threading.Lock()
        self.active_jobs = {}
        
        self.db_session = None
        if DB_AVAILABLE and db_url:
            try:
                self.db_session, _ = create_db_session(db_url)
                print("[SERVER] Connected to database for Live Rolling Aggregation.")
            except Exception as e:
                print(f"[SERVER WARNING] DB connection failed: {e}")

    def _get_or_create_job(self, job_id):
        """Creates a continuous rolling state dictionary for the specific Job ID."""
        if job_id not in self.active_jobs:
            expected_clients = 1
            if self.db_session and job_id:
                try:
                    config = fetch_job_config(self.db_session, job_id)
                    expected_clients = config.get("expected_clients", 1)
                    update_job_status(self.db_session, job_id, "running")
                except:
                    pass

            self.active_jobs[job_id] = {
                "rolling_global_state_dict": {},
                "rolling_total_samples": 0,
                "participating_clients": set(),
                "total_updates_processed": 0,
                "client_rounds": {},
                "expected_clients": expected_clients # <--- Save it here!
            }
        return self.active_jobs[job_id]

    def SubmitWeightUpdate(self, request, context):
        with self.lock:
            job_id = getattr(request, 'job_id', 0)
            if len(request.layers) > 0:
                return self._handle_structured_rolling(request, job_id)
            else:
                return federation_pb2.UpdateAck(success=False, message="Only structured payloads are supported in rolling mode.")

    def _handle_structured_rolling(self, request, job_id):
        job_state = self._get_or_create_job(job_id)
        
        
        # 1. Parse incoming payload
        state_dict = {}
        for tensor in request.layers:
            state_dict[tensor.layer_name] = {
                "data": list(tensor.data),
                "shape": list(tensor.shape),
            }

        # --- SERVER TRACKING (For the Graph) ---
        job_state["total_updates_processed"] += 1
        global_step = job_state["total_updates_processed"]
        expected_clients = job_state["expected_clients"]
        global_round = ((global_step - 1) // expected_clients) + 1
        job_state["participating_clients"].add(request.client_id)
        new_samples = request.sample_count

        # --- CLIENT TRACKING (For the Table) ---
        if request.client_id not in job_state["client_rounds"]:
            job_state["client_rounds"][request.client_id] = 0
        job_state["client_rounds"][request.client_id] += 1
        
        client_local_round = job_state["client_rounds"][request.client_id]

        # Write receipt to database to unlock UI and show Client metrics
        if self.db_session:
            try:
                record_client_submission(
                    session=self.db_session,
                    job_id=job_id,
                    client_id_str=request.client_id,
                    round_number=client_local_round, # <--- Pass the Local Round!
                    sample_count=new_samples,
                    state_dict=state_dict
                )
            except Exception as e:
                print(f"[SERVER WARNING] Failed to record client submission: {e}")

        print(f"\n[SERVER|Job:{job_id}] Received update from {request.client_id} (Samples: {new_samples})")

        # 2. Mathematical Rolling Average
        if not job_state["rolling_global_state_dict"]:
            job_state["rolling_global_state_dict"] = state_dict
            job_state["rolling_total_samples"] = new_samples
            print(f"[SERVER|Job:{job_id}] Initialized new Global Model baseline.")
        else:
            old_total = job_state["rolling_total_samples"]
            new_total = old_total + new_samples
            
            for layer in state_dict:
                if layer in job_state["rolling_global_state_dict"]:
                    for i in range(len(state_dict[layer]["data"])):
                        old_val = job_state["rolling_global_state_dict"][layer]["data"][i]
                        new_val = state_dict[layer]["data"][i]
                        job_state["rolling_global_state_dict"][layer]["data"][i] = ((old_val * old_total) + (new_val * new_samples)) / new_total
            
            job_state["rolling_total_samples"] = new_total
            print(f"[SERVER|Job:{job_id}] Rolled new weights into Global Model. Total Network Samples: {new_total}")

        # 3. Build Snapshot and Save Global Metrics
        snapshot_data = {
            layer: {
                "shape": info["shape"],
                "mean": sum(info["data"]) / max(len(info["data"]), 1),
                "num_params": len(info["data"]),
            }
            for layer, info in job_state["rolling_global_state_dict"].items()
        }
        # Inject the client labels so the React Tooltip works!
        snapshot_data["client_labels"] = list(job_state["participating_clients"])

        self._record_metrics_to_db(
            job_id=job_id,
            current_round=global_round, # <--- FIX: Use the mathematically correct round!
            num_clients=len(job_state["participating_clients"]),
            total_samples=job_state["rolling_total_samples"],
            global_weights_snapshot=snapshot_data
        )

        return federation_pb2.UpdateAck(
            success=True,
            message=f"Live Aggregation Complete! Folded {new_samples} samples into Job {job_id}."
        )

    def _record_metrics_to_db(self, job_id, current_round, num_clients, total_samples, global_weights_snapshot):
        if not self.db_session or not job_id:
            return
        try:
            record_round_metric(
                session=self.db_session,
                job_id=job_id,
                round_number=current_round,
                num_clients=num_clients,
                total_samples=total_samples,
                global_weights_snapshot=global_weights_snapshot,
            )
        except Exception as e:
            print(f"[SERVER WARNING] DB Write Failed: {e}")


def serve(db_url: str = None, port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    federation_pb2_grpc.add_AggregatorServicer_to_server(
        AggregatorServicer(db_url=db_url),
        server,
    )
    server.add_insecure_port(f'[::]:{port}')
    print(f"[SERVER] gRPC Aggregator listening on port {port}...")
    print("[SERVER] Operating in Multi-Tenant Mode")
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="FederHub Gamma gRPC aggregation server")
    parser.add_argument("--port", type=int, default=int(os.getenv("GRPC_PORT", "50051")))
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()

    serve(
        db_url=args.db_url or None,
        port=args.port,
    )