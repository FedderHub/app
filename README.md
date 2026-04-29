# FederHub Merged Integration

This repository combines the Phase 2 work from the three teams into one project:

- `backend/` - Team Alpha FastAPI API, PostgreSQL/RDS schema, JWT auth, job APIs, and metrics APIs.
- `frontend/` - Team Alpha React dashboard with job creation, job start, and round metric visibility.
- `client/` - Team Beta Electron edge-node app, Docker sandbox, local PyTorch training, and gRPC weight streaming.
- `federated-engine/` - Team Gamma gRPC aggregator, FedAvg implementation, Celery worker, and RDS metrics connector.

## Environment

The canonical database is Alpha's AWS RDS PostgreSQL instance. Keep credentials in env files only.

`backend/.env` should contain:

```bash
DATABASE_URL=postgresql://postgres:<real-password>@federhub-db.cq326a2yexwu.us-east-1.rds.amazonaws.com:5432/federhub
SECRET_KEY=<local-development-secret>
REDIS_URL=redis://localhost:6379/0
```

`federated-engine/.env` can use the same `DATABASE_URL` and `REDIS_URL` values:

```bash
DATABASE_URL=postgresql://postgres:<real-password>@federhub-db.cq326a2yexwu.us-east-1.rds.amazonaws.com:5432/federhub
REDIS_URL=redis://localhost:6379/0
EXPECTED_CLIENTS=3
GRPC_PORT=50051
```

## RDS Migration

Alpha's Phase 2 schema is preserved. The integrated project adds Gamma's `round_metrics` table.

After replacing `pass` in `backend/.env` with the real password, run:

```bash
cd backend
set -a
source .env
set +a
psql "$DATABASE_URL" -f migrations/phase2_rds_upgrade.sql
psql "$DATABASE_URL" -f migrations/phase3_integration.sql
```

The FastAPI app and Gamma engine also call SQLAlchemy `create_all`/table creation as a fallback, but the SQL files are the clean migration path for RDS.

## Run Locally

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm start
```

Gamma gRPC aggregator for a specific job:

```bash
cd federated-engine
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python grpc_server.py --job-id <job_id> --expected-clients 3 --port 50051
```

Gamma Celery worker:

```bash
cd federated-engine
source .venv/bin/activate
celery -A celery_app worker --loglevel=info
```

Beta client:

```bash
cd client
npm install
npm start
```

## Integrated Flow

1. Create/login as an ML Engineer in the web app.
2. Create a training job in the dashboard.
3. Click `Start Orchestration`; the API marks the job scheduled and queues Gamma's Celery task if Redis is available.
4. Start Gamma's gRPC aggregator with that job ID.
5. In the Electron client, authenticate against the Alpha API, select a `.pt` checkpoint and local CSV folder, then start training.
6. The client trains inside Docker with the dataset mounted read-only and streams only model weights to Gamma.
7. Gamma runs FedAvg when the expected clients have submitted updates and writes round metrics into RDS.
8. The React dashboard reads `/jobs/{job_id}/metrics` to show completed round progress.
