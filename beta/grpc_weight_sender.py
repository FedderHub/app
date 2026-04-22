# grpc_weight_sender.py
# ======================
# FederHub - Team Beta × Team Gamma | Phase 3
# --------------------------------------------
# After local PyTorch training completes, this module loads the saved
# model checkpoint (.pt file), serializes the state_dict into Protobuf
# TensorData messages, and streams only the mathematical weight updates
# to Team Gamma's gRPC aggregation server.
#
# No raw patient/financial data ever leaves the client — only model
# parameters are transmitted.
#
# Usage:
#   python grpc_weight_sender.py \
#       --pt-file output/updated_model.pt \
#       --summary-file output/run_summary.json \
#       --server localhost:50051 \
#       --client-id "Hospital A"

import argparse
import json
import sys
from pathlib import Path

try:
    import torch
except ImportError:
    print("[SENDER ERROR] PyTorch is required. Install with: pip install torch")
    sys.exit(1)

import grpc

current_dir = Path(__file__).resolve().parent
candidate_proto_dirs = [
    current_dir / "gama" / "phase2",
    current_dir.parent / "gama" / "phase2",
]

for proto_dir in candidate_proto_dirs:
    if proto_dir.exists():
        sys.path.insert(0, str(proto_dir))
        break

import federation_pb2
import federation_pb2_grpc


def load_state_dict(pt_path: str) -> dict:
    """Load a PyTorch state_dict from a .pt checkpoint file."""
    checkpoint = torch.load(pt_path, map_location="cpu", weights_only=True)

    # Handle both raw state_dict and wrapped checkpoint formats
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        return checkpoint["state_dict"]
    return checkpoint


def get_sample_count(summary_path: str) -> int:
    """Read the sample count from a run_summary.json file."""
    if not summary_path or not Path(summary_path).exists():
        print("[SENDER WARNING] No run_summary.json found. Using default sample count of 100.")
        return 100

    with open(summary_path, "r") as f:
        summary = json.load(f)

    # Try to read sample count from the summary
    # Beta's run_summary.json doesn't currently include sample count,
    # so we read the dataset CSV to count rows if available
    dataset_path = summary.get("dataset", "")
    if dataset_path and Path(dataset_path).exists():
        try:
            with open(dataset_path, "r") as csv_f:
                # Subtract 1 for header row
                count = sum(1 for _ in csv_f) - 1
                return max(count, 1)
        except Exception:
            pass

    return 100  # Default fallback


def state_dict_to_proto_layers(state_dict: dict) -> list:
    """Convert a PyTorch state_dict into a list of TensorData protos."""
    layers = []
    for layer_name, tensor in state_dict.items():
        tensor_data = federation_pb2.TensorData(
            layer_name=str(layer_name),
            shape=list(tensor.shape),
            data=tensor.flatten().tolist(),
        )
        layers.append(tensor_data)
    return layers


def describe_model(state_dict: dict) -> str:
    """Generate a human-readable architecture summary from the state_dict."""
    parts = []
    for name, tensor in state_dict.items():
        parts.append(f"{name}: {list(tensor.shape)}")
    return " | ".join(parts)


def send_weights(
    pt_path: str,
    summary_path: str,
    server_address: str,
    client_id: str,
) -> bool:
    """
    Load a .pt file and send the weights to Gamma's gRPC server.

    Args:
        pt_path: Path to the .pt checkpoint file.
        summary_path: Path to run_summary.json (for sample count).
        server_address: Gamma server address (e.g. "localhost:50051").
        client_id: Identifier for this edge node (e.g. "Hospital A").

    Returns:
        True if the submission was acknowledged, False otherwise.
    """
    # 1. Load the model weights
    print(f"[SENDER] Loading checkpoint: {pt_path}")
    state_dict = load_state_dict(pt_path)

    total_params = sum(t.numel() for t in state_dict.values())
    print(f"[SENDER] Model loaded: {len(state_dict)} layers, {total_params} parameters.")

    # 2. Get sample count
    sample_count = get_sample_count(summary_path)
    print(f"[SENDER] Sample count: {sample_count}")

    # 3. Serialize into protobuf
    layers = state_dict_to_proto_layers(state_dict)
    architecture = describe_model(state_dict)

    request = federation_pb2.WeightUpdate(
        client_id=client_id,
        sample_count=sample_count,
        layers=layers,
        model_architecture=architecture,
    )

    # 4. Send to Gamma's server
    print(f"[SENDER] Connecting to Gamma aggregation server at {server_address}...")
    channel = grpc.insecure_channel(server_address)
    stub = federation_pb2_grpc.AggregatorStub(channel)

    try:
        response = stub.SubmitWeightUpdate(request, timeout=30)
        print(f"[SENDER] Server response: {response.message}")
        channel.close()
        return response.success
    except grpc.RpcError as e:
        print(f"[SENDER ERROR] gRPC call failed: {e.code()} - {e.details()}")
        channel.close()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="FederHub Phase 3: Stream trained PyTorch weights to Gamma's aggregation server"
    )
    parser.add_argument(
        "--pt-file", required=True,
        help="Path to the .pt checkpoint file containing trained model weights"
    )
    parser.add_argument(
        "--summary-file", default="",
        help="Path to run_summary.json (used to determine sample count)"
    )
    parser.add_argument(
        "--server", default="localhost:50051",
        help="Gamma gRPC server address (default: localhost:50051)"
    )
    parser.add_argument(
        "--client-id", required=True,
        help="Identifier for this edge node (e.g. 'Hospital A')"
    )
    args = parser.parse_args()

    success = send_weights(
        pt_path=args.pt_file,
        summary_path=args.summary_file,
        server_address=args.server,
        client_id=args.client_id,
    )

    if success:
        print("[SENDER] Weight submission complete. Only mathematical updates were transmitted.")
    else:
        print("[SENDER] Weight submission failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
