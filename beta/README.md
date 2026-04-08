# FederHub Team Beta Phase 2

This folder contains the current Team Beta Phase 2 edge-node application.

## What is included

- An Electron desktop client for the local operator workflow
- Dockerized training with a read-only dataset mount
- PyTorch checkpoint selection and inspection
- Checkpoint-aware CSV schema validation
- Synthetic healthcare demo bundles for fracture and tumor detection

## Folder layout

- `main.js`: Electron main process and Docker execution flow
- `preload.js`: secure bridge between the renderer and Electron APIs
- `Dockerfile`: container image for the training worker
- `requirements.txt`: Python dependencies used inside the container
- `src/`: desktop UI files
- `ml/train.py`: checkpoint-aware training worker
- `ml/inspect_checkpoint.py`: reads `.pt` metadata to infer dataset requirements
- `demo-client-data/`: sample datasets and checkpoints for demos

## Prerequisites

1. Install Node.js and npm.
2. Install Python 3.
3. Install Docker Desktop and ensure the `docker` CLI is available.
4. Install Electron dependencies from this folder:

```bash
npm install
```

## Run the desktop client

```bash
npm start
```

## Demo bundles

- `demo-client-data/fracture-detection/`
  - `fracture_dataset.csv`
  - `fracture_model.pt`
- `demo-client-data/tumor-detection/`
  - `tumor_dataset.csv`
  - `tumor_model.pt`
- `demo-client-data/sample_client_data.csv`
  - `demo-client-data/sample_model.pt`

## Desktop flow

1. Launch the Electron app.
2. Enter operator credentials.
3. Choose a `.pt` checkpoint file.
4. Choose the matching dataset folder.
5. Review the inferred dataset requirements in the UI.
6. Click `Start Training`.

## Output artifacts

The app writes updated weights and a run summary to the Electron user-data output directory. Updated checkpoints are saved as `updated_<original-checkpoint-name>.pt`.

## Notes

- The password field is collected in the UI only; it is not connected to backend authentication in Phase 2.
- The selected dataset folder is mounted read-only into Docker so source data remains local during training.
