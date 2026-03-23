import argparse
import csv
import json
from pathlib import Path

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError as exc:
    raise SystemExit(
        "PyTorch is not installed. Install it with `pip install torch` before running training."
    ) from exc


def load_dataset(csv_path: Path):
    features = []
    labels = []

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            features.append(
                [
                    float(row["feature_1"]),
                    float(row["feature_2"]),
                    float(row["feature_3"]),
                    float(row["feature_4"]),
                ]
            )
            labels.append(float(row["label"]))

    x_tensor = torch.tensor(features, dtype=torch.float32)
    y_tensor = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)
    return TensorDataset(x_tensor, y_tensor)


def train_model(dataset: TensorDataset, epochs: int):
    loader = DataLoader(dataset, batch_size=4, shuffle=True)
    model = nn.Sequential(
        nn.Linear(4, 8),
        nn.ReLU(),
        nn.Linear(8, 1),
        nn.Sigmoid(),
    )

    loss_fn = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.03)

    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        correct_predictions = 0
        total_examples = 0

        for batch_inputs, batch_labels in loader:
            optimizer.zero_grad()
            outputs = model(batch_inputs)
            loss = loss_fn(outputs, batch_labels)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * len(batch_inputs)
            predictions = (outputs >= 0.5).float()
            correct_predictions += (predictions == batch_labels).sum().item()
            total_examples += len(batch_inputs)

        accuracy = correct_predictions / total_examples
        average_loss = epoch_loss / total_examples
        print(
            f"Epoch {epoch:02d} | loss={average_loss:.4f} | accuracy={accuracy:.2%}",
            flush=True,
        )

    return model


def flush_sensitive_tensors(*tensors):
    for tensor in tensors:
        if tensor is not None:
            tensor.zero_()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def main():
    parser = argparse.ArgumentParser(description="FederHub Team Beta Phase 1 trainer")
    parser.add_argument("--data", required=True, help="Path to the dummy CSV dataset")
    parser.add_argument("--output-dir", required=True, help="Directory for saved model files")
    parser.add_argument(
        "--selected-folder",
        default="",
        help="Folder selected in the desktop client for local data mapping",
    )
    parser.add_argument("--epochs", type=int, default=8, help="Number of local training epochs")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("FederHub Beta trainer starting...", flush=True)
    print(f"Dataset: {data_path}", flush=True)
    print(
        f"Selected local folder: {args.selected_folder or '[not provided in this demo]'}",
        flush=True,
    )

    dataset = load_dataset(data_path)
    training_inputs = dataset.tensors[0].clone()
    training_labels = dataset.tensors[1].clone()
    training_dataset = TensorDataset(training_inputs, training_labels)

    model = train_model(training_dataset, args.epochs)

    weights_path = output_dir / "model.pt"
    metadata_path = output_dir / "run_summary.json"
    torch.save(model.state_dict(), weights_path)

    metadata = {
        "weights_path": str(weights_path),
        "epochs": args.epochs,
        "selected_folder": args.selected_folder,
        "dataset": str(data_path),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    flush_sensitive_tensors(training_inputs, training_labels)

    print(f"Saved weights to: {weights_path}", flush=True)
    print(f"Saved run summary to: {metadata_path}", flush=True)
    print(
        "Memory flush step completed for in-process training tensors. Only model weights remain.",
        flush=True,
    )


if __name__ == "__main__":
    main()
