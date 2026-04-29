# FederHub Merged Integration

This repository combines the Phase 2 work from the three teams into one project:

- `backend/` - Team Alpha FastAPI API, PostgreSQL/RDS schema, JWT auth, job APIs, and metrics APIs.
- `frontend/` - Team Alpha React dashboard with role-aware job creation, start, client update submission, FedAvg results, and admin controls.
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
psql "$DATABASE_URL" -f migrations/phase4_website_workflow.sql
psql "$DATABASE_URL" -f migrations/phase5_publish_results.sql
psql "$DATABASE_URL" -f migrations/phase6_job_description_weight_count.sql
```

The FastAPI app also calls SQLAlchemy `create_all` as a fallback, but the SQL files are the clean migration path for RDS.

## Run Locally

Run the backend and frontend in **two separate Terminal windows**.

Terminal 1 - Backend:

```bash
cd "/Users/naman/1)Projects/NYU projects/Federhub-all branches/merged/backend" && source .venv/bin/activate && uvicorn app.main:app --reload
```

Terminal 2 - Frontend:

```bash
cd "/Users/naman/1)Projects/NYU projects/Federhub-all branches/merged/frontend" && npm start
```

Then open `http://localhost:3000`.

Optional Beta/Gamma local training bridge:

```bash
cd client
npm install
npm start
```

## Integrated Flow

1. Create/login as an ML Engineer in the web app.
2. Create a training job in the dashboard.
3. Click `Start Orchestration`; the API marks the job running.
4. Log in as a Client Operator.
5. Open a running job card and submit a local update payload: client label, sample count, optional accuracy/loss, and model weights.
6. When the configured number of clients submit for the active round, the backend runs FedAvg and writes a `round_metrics` row in RDS.
7. The job advances to the next round or becomes completed after the configured final round.
8. Admin and ML Engineer dashboards show creator, active round, pending updates, client count, total samples, and aggregate metrics.

This browser workflow is the professor-demo path. The Electron client and Gamma gRPC engine remain available for deeper local-training demos, but users do not need terminal job IDs for the website product flow.
