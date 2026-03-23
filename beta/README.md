# FederHub Team Beta Phase 1

This folder contains a self-contained prototype for Team Beta's Phase 1 scope from the project blueprint.

## What is included

- A basic Electron desktop shell
- A local folder picker
- A standalone PyTorch training script
- A dummy CSV dataset
- Output artifacts for model weights and a run summary

## Folder layout

- `main.js`: Electron main process and IPC handlers
- `preload.js`: safe bridge from the renderer to Electron APIs
- `src/`: desktop UI files
- `ml/train.py`: local training worker
- `ml/data/dummy.csv`: demo dataset
- `ml/output/`: generated weights and run summaries

## Prerequisites

1. Install Node.js and npm.
2. Install Python 3.
3. Install PyTorch:

```bash
pip install torch
```

4. Install Electron dependencies from this folder:

```bash
npm install
```

## Run the desktop client

```bash
npm start
```

## Run only the Python worker

```bash
python ml/train.py --data ml/data/dummy.csv --output-dir ml/output
```

## Demo flow

1. Launch the Electron app.
2. Choose a local folder.
3. Click `Start Local Training`.
4. Review logs in the output panel.
5. Check `ml/output/` for `model.pt` and `run_summary.json`.

## Phase 1 notes

- The login UI is intentionally local-only and does not call a backend yet.
- The selected folder is captured for the future Docker-mounting flow in Phase 2.
