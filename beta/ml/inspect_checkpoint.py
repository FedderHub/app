import json
import sys
from pathlib import Path

try:
    import torch
except Exception as exc:
    print(
        json.dumps(
            {
                "ok": False,
                "columns": [],
                "summary": (
                    f"Unable to inspect checkpoint: {exc}. "
                    "Expected CSV columns remain feature_1, feature_2, feature_3, feature_4, label."
                ),
            }
        )
    )
    raise SystemExit(0)


def main():
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "ok": False,
                    "columns": [],
                    "summary": (
                        "No checkpoint path was provided. "
                        "Expected CSV columns remain feature_1, feature_2, feature_3, feature_4, label."
                    ),
                }
            )
        )
        return

    path = Path(sys.argv[1]).resolve()

    try:
        checkpoint = torch.load(path, map_location="cpu")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "columns": [],
                    "summary": (
                        f"Checkpoint could not be read: {exc}. "
                        "Expected CSV columns remain feature_1, feature_2, feature_3, feature_4, label."
                    ),
                }
            )
        )
        return

    metadata = checkpoint if isinstance(checkpoint, dict) else {}
    input_columns = metadata.get("input_columns") or metadata.get("feature_columns") or []
    label_column = metadata.get("label_column") or "label"

    if input_columns:
        columns = input_columns + [label_column]
        print(
            json.dumps(
                {
                    "ok": True,
                    "columns": columns,
                    "summary": "Checkpoint metadata found. CSV should contain: " + ", ".join(columns) + ".",
                }
            )
        )
        return

    state_dict = metadata.get("state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
    first_weight = None
    if isinstance(state_dict, dict):
        for value in state_dict.values():
            if hasattr(value, "shape") and len(value.shape) == 2:
                first_weight = value
                break

    if first_weight is not None:
        in_features = int(first_weight.shape[1])
        columns = [f"feature_{i}" for i in range(1, in_features + 1)] + ["label"]
        print(
            json.dumps(
                {
                    "ok": True,
                    "columns": columns,
                    "summary": (
                        f"Checkpoint expects {in_features} numeric input features. "
                        "CSV should contain: "
                        + ", ".join(columns)
                        + "."
                    ),
                }
            )
        )
        return

    print(
        json.dumps(
            {
                "ok": False,
                "columns": [],
                "summary": (
                    "Checkpoint loaded, but its input shape could not be inferred. "
                    "Expected CSV columns remain feature_1, feature_2, feature_3, feature_4, label."
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
