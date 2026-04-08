# FederHub — Team Alpha (Phase 2)

## Prerequisites

- Python 3.9+
- Node.js 18+
- npm
- AWS RDS PostgreSQL instance (port 5432 must be open in the security group)

---

## Backend (FastAPI)

### 1. Navigate to the backend folder
```bash
cd backend
```

### 2. Activate the virtual environment
```bash
source federhub/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

The `.env` file is not committed to GitHub for security reasons. Create one in the `backend/` folder:
```bash
touch .env
```

Add the following line with your RDS credentials:
```
DATABASE_URL=postgresql://postgres:<password>@federhub-db.cq326a2yexwu.us-east-1.rds.amazonaws.com:5432/federhub
```

> **Note:** The AWS RDS security group must have an inbound rule allowing TCP on port 5432 from your IP (or `0.0.0.0/0` for development).

### 5. Start the server
```bash
python3 -m uvicorn app.main:app --reload
```

The API will be running at `http://127.0.0.1:8000`.

Interactive API docs are available at `http://127.0.0.1:8000/docs`.

---

## Frontend (React)

Open a new terminal tab/window.

### 1. Navigate to the frontend folder
```bash
cd frontend
```

### 2. Install dependencies
```bash
npm install
```

### 3. Start the development server
```bash
npm start
```

The app will open at `http://localhost:3000`.

---

## Usage

1. Go to `http://localhost:3000/register` and create an account. Available roles:
   - `ML Engineer` — can create and view training jobs
   - `Platform Admin` — full access
   - `Client Operator` — view-only access

2. Log in at `http://localhost:3000/login`

3. From the dashboard, click **Create Job** to configure a new federated training job with:
   - **Job Name** — a unique identifier for the training run
   - **Round Count** — number of global FedAvg aggregation rounds
   - **Local Epochs** — epochs each client trains before sending weight updates

4. Created jobs are saved to the RDS database and visible on the dashboard.

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | None | Register a new user |
| POST | `/auth/login` | None | Login and receive JWT token |
| GET | `/auth/me` | JWT | Get current user profile |
| GET | `/jobs/` | JWT | List all training jobs |
| POST | `/jobs/` | JWT (admin/ml_engineer) | Create a new training job |
| GET | `/jobs/{id}` | JWT | Get a specific job |
| PATCH | `/jobs/{id}/status` | JWT (admin/ml_engineer) | Update job status |
| GET | `/health` | None | Health check |

---

## Project Structure

```
app/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app entry point
│   │   ├── models.py        # SQLAlchemy database models
│   │   ├── schemas.py       # Pydantic request/response schemas
│   │   ├── auth.py          # JWT utilities and role guards
│   │   ├── db.py            # Database connection
│   │   ├── config.py        # Environment config
│   │   └── routers/
│   │       ├── auth.py      # /auth endpoints
│   │       └── jobs.py      # /jobs endpoints
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.js            # Router setup
        ├── api/client.js     # Axios instance with JWT interceptor
        ├── pages/
        │   ├── LoginPage.js
        │   ├── RegisterPage.js
        │   ├── Dashboard.js
        │   └── CreateJobPage.js
        └── components/
            ├── Navbar.js
            └── PrivateRoute.js
```
