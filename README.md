# FederHub — Team Alpha (Phase 3)

FastAPI backend + React frontend for the FederHub central platform.

---

## Prerequisites

- Python 3.9+
- Node.js 18+
- npm
- AWS RDS PostgreSQL (port 5432 open in security group)

---

## Running the Backend

```bash
cd backend
source federhub/bin/activate
pip install -r requirements.txt
```

Create a `.env` file inside `backend/`:
```
DATABASE_URL=postgresql://postgres:<password>@federhub-db.cq326a2yexwu.us-east-1.rds.amazonaws.com:5432/federhub
```

If this is your first time running Phase 3, apply the migration on your RDS instance:
```
backend/migrations/phase3_rds_upgrade.sql
```

Then start the server:
```bash
python3 -m uvicorn app.main:app --reload
```

API runs at `http://127.0.0.1:8000`. Docs at `http://127.0.0.1:8000/docs`.

---

## Running the Frontend

```bash
cd frontend
npm install
npm start
```

Opens at `http://localhost:3000`.

---

## Usage

- Register at `/register` — pick a role: ML Engineer, Platform Admin, or Client Operator
- Log in at `/login` with your email and password
- Create a training job from the dashboard — set job name, round count, and local epochs
- Click any job to see round-by-round accuracy metrics posted by Team Gamma

---

## Integration — Team Beta

The Electron app logs in by sending `username` + `password` to `POST /auth/login` instead of email. Both formats are accepted.

```json
{ "username": "client.operator", "password": "your-password" }
```

---

## Integration — Team Gamma

After each FedAvg aggregation round, Gamma posts results using a service key header. Job status updates automatically as rounds come in.

```
POST /jobs/{job_id}/rounds
X-Service-Key: federhub-gamma-service-key-change-in-production

{ "round_number": 1, "global_accuracy": 0.87, "num_clients": 3 }
```

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | None | Register a new user |
| POST | `/auth/login` | None | Login by email or username |
| GET | `/auth/me` | JWT | Current user profile |
| GET | `/jobs/` | JWT | List all jobs |
| POST | `/jobs/` | JWT | Create a job |
| GET | `/jobs/{id}` | JWT | Get a job |
| PATCH | `/jobs/{id}/status` | JWT | Update job status |
| POST | `/jobs/{id}/rounds` | Service key | Post round metrics (Gamma) |
| GET | `/jobs/{id}/rounds` | JWT | Get round metrics for a job |
| GET | `/health` | None | Health check |

---

## Project Structure

```
app/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── auth.py
│   │   ├── db.py
│   │   ├── config.py
│   │   └── routers/
│   │       ├── auth.py
│   │       └── jobs.py
│   ├── migrations/
│   │   ├── phase2_rds_upgrade.sql
│   │   └── phase3_rds_upgrade.sql
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.js
        ├── api/client.js
        ├── pages/
        │   ├── LoginPage.js
        │   ├── RegisterPage.js
        │   ├── Dashboard.js
        │   ├── CreateJobPage.js
        │   └── JobDetailPage.js
        └── components/
            ├── Navbar.js
            └── PrivateRoute.js
```
