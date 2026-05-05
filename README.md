# FederHub: Federated Learning Platform

FederHub is a decentralized, privacy-preserving Machine Learning architecture. It bridges a React/FastAPI web dashboard with a secure, Electron-based Edge Node desktop application running local PyTorch models inside Docker, all orchestrated by a Python gRPC/Celery backend.

---

## What Changes We Made & Why

1. **Live Rolling-Basis Aggregation**
   * **What:** Shifted the Gamma gRPC server from a "wait for everyone" batch system to a continuous learning model. The engine now applies a Weighted Moving Average the instant *any* client submits weights, and the React UI polls every 3 seconds to animate the graph in real-time.
   * **Why:** To drastically speed up the feedback loop and allow asynchronous nodes to contribute without bottlenecking the entire network.
2. **Secure Client ID Auto-Injection**
   * **What:** Stripped the manual "Client ID" input from the Edge Node UI. The Electron backend now securely extracts the authenticated User ID from the session token and injects it directly into the Python training scripts.
   * **Why:** To prevent users from spoofing their identities and to ensure the backend database can perfectly track which node submitted which weights.
3. **Live Analytics Dashboard (React)**
   * **What:** Upgraded the Job Details page to include synchronized multi-line Recharts graphs tracking Global Accuracy, Loss, and exact parameter weight changes across FedAvg rounds. Added custom tooltips showing contributing Client IDs.
   * **Why:** To provide ML Engineers and Client Operators with real-time, transparent insights into model convergence.
4. **Native App Distribution**
   * **What:** Added a FastAPI download endpoint and web dashboard buttons to serve compiled `.dmg` (Mac) and `.exe` (Windows) installer files.
   * **Why:** To simulate a true commercial SaaS workflow where hospitals can securely download the Edge Node software directly from the portal.
5. **Zero-Trust Docker Architecture (Electron)**
   * **What:** Re-architected the desktop client to rely entirely on a pre-built Docker image rather than building images dynamically on the user's machine. 
   * **Why:** To make the desktop application infinitely more reliable, faster, and immune to local OS environment bugs.
6. **Multi-Tenant gRPC Orchestration Engine**
   * **What:** Upgraded the Gamma server to utilize a dynamic "Job State Dictionary" rather than flat global variables. 
   * **Why:** To allow the server to process dozens of different machine learning models (e.g., Tumor Detection and Bone Fracture Analysis) simultaneously without cross-contaminating the mathematical weights.
7. **End-to-End Job Routing**
   * **What:** Wired a `Target Job ID` field from the React UI -> Electron Payload -> Docker Arguments -> `train.py` -> `grpc_weight_sender.py` -> Protobuf schema -> gRPC Server.
   * **Why:** To guarantee every packet of weights is mathematically isolated and properly attributed to its specific job in the PostgreSQL database.
8. **Zero-Knowledge Privacy Controls (FastAPI)**
   * **What:** Updated the API router to verify the `current_user.id` against the `ClientSubmissions` table before serving job details. 
   * **Why:** To ensure new users or "free-riders" cannot view the proprietary Global Model weights or analytics until they have actively contributed their own local data to the training round.

---

## Issues Faced & How We Resolved Them

Building a desktop app that orchestrates Docker and Python introduced severe macOS security constraints, and scaling to a multi-tenant environment required complex state management. Here is the breakdown of the roadblocks and our engineering solutions:

### Issue 1: The `spawn ENOTDIR` Crash (PATH Resolution)
* **The Problem:** When running from a `.dmg`, macOS strips the application's environment `PATH`. Electron could not find Python or Docker, crashing instantly.
* **The Fix:** We injected a macOS-specific patch at the top of `main.js` to explicitly rebuild `process.env.PATH` with default system locations (`/usr/local/bin`, `/opt/homebrew/bin`).

### Issue 2: "Returned no data" (The ASAR Vault Lockout)
* **The Problem:** Electron packages all code into a highly compressed, read-only `app.asar` archive. When we told Docker/Python to run our ML scripts, they failed silently because external programs cannot read inside an `.asar` file.
* **The Fix:** We updated `package.json` with an `"asarUnpack"` rule, forcing Electron to leave the `ml/` scripts, `demo-client-data/`, and `Dockerfile` unpacked and accessible to the host system.

### Issue 3: Docker Buildx/BuildKit Deadlock
* **The Problem:** We initially tried to run `docker build` inside the desktop app. macOS security sandboxing explicitly blocks `.dmg` applications from reading hidden folders like `~/.docker`. Docker panicked when it couldn't find its build plugins and blocked the execution.
* **The Fix:** We pivoted to a **Pre-built Container Architecture**. We completely removed the `docker build` command from the client code. Instead, the ML Engineer builds the image once, and the client app only uses `docker run`.

### Issue 4: Docker Entrypoint Overlap
* **The Problem:** When trying to validate a PyTorch model via `docker run federhub-beta-trainer python3 inspect.py`, the container crashed. The `Dockerfile` had a hardcoded `ENTRYPOINT` locking it to the `train.py` script.
* **The Fix:** We updated the validation spawn command to include the `--entrypoint python3` flag, dynamically bypassing the Dockerfile lock to execute the inspection script cleanly.

### Issue 5: The "Blind Catcher" Aggregation Bug
* **The Problem:** The gRPC server was indiscriminately grabbing weights from any node that submitted them, mixing Tumor Detection weights with Bone Fracture weights into a corrupted global model.
* **The Fix:** Re-wrote `grpc_server.py` to intercept the `job_id` from the Protobuf request and route incoming tensors into isolated, dynamically generated state dictionaries. 

### Issue 6: UI Ghost Data & Database Desync
* **The Problem:** Transitioning to Rolling Aggregation caused internal round counters to desync from historical database records, resulting in "N/A" metrics, "Unknown Clients" in the UI, and crashed SQLite transactions.
* **The Fix:** We decoupled the Global Step tracker from the Local Client Round tracker inside the gRPC server, updated the database connector to safely rollback crashed sessions, and injected simulated local metric placeholders into the database receipt to keep the UI graphs perfectly populated.

---

##  Step-by-Step Execution Guide

Follow these steps exactly to run the full, end-to-end multi-tenant Federated Learning pipeline. You will need 5 terminal windows to run the complete microservice architecture.

### Step 1: Pre-Build the Docker Image (Admin Setup)
Before any client can train, the core ML environment must be built on the host machine.
1. Open your terminal.
2. Navigate to your **main project root folder** (the folder containing both `client` and `federated-engine`).
3. Run this command to build the Gold Master image:
   ```bash
   docker build -t federhub-beta-trainer -f client/Dockerfile .
   ```

### Step 2: Start the Gamma Orchestration Engine
This is the core network that catches client weights and runs FedAvg aggregation. *(Ensure Redis is running in the background).*
1. **Start the gRPC Server:** Open a new terminal, navigate to `federated-engine`, activate your `.venv`, and run:
   ```bash
   python grpc_server.py
   ```
2. **Start the Celery Worker:** Open a new terminal, navigate to `federated-engine`, activate your `.venv`, and run:
   ```bash
   celery -A celery_app worker --loglevel=info
   ```

### Step 3: Start the Web Infrastructure
You need both the API and the React frontend running to manage jobs and view analytics.
1. **Start the Backend:** Open a new terminal, navigate to the `backend` folder, activate your `.venv`, and run:
   ```bash
   python3 -m uvicorn app.main:app --reload
   ```
2. **Start the Frontend:** Open a new terminal, navigate to the `frontend` folder, and run:
   ```bash
   npm start
   ```
   *(This will open `http://localhost:3000` in your browser).*

### Step 4: Configure the Federated Jobs
1. Log into the web dashboard as an **ML Engineer** (`engineer@test.com` / `password123`).
2. Click **+ Create Job** and configure a Tumor Detection job (e.g., Name: `Tumor Detection`, Rounds: `3`, Expected Clients: `2`, Required Weights: `49`).
3. Click **Start Orchestration** on the job card. **Note the distinct Job ID assigned to it.**

### Step 5: Package and Host the Desktop Client
Because large binaries (`.dmg`/`.exe`) are excluded from Git, the Admin must compile and host the app manually.
1. Open a new terminal and navigate to the `client` folder.
2. Package the app into a production `.dmg` file:
   ```bash
   npm run pack:mac
   ```
3. Locate the compiled `.dmg` inside `client/dist/`. 
4. **Rename it** to `FederHub-Edge-Client.dmg` and **move it** into the `backend/downloads/` folder. 
5. Users can now click the download button on the React dashboard to receive the app!

### Step 6: Execute Multi-Node Training
1. In the downloaded Edge Node app, log in as the **Client Operator** (`hospital@test.com` / `password123`).
2. **Set Target Job ID:** Enter the ID matching the Tumor job (e.g., `1`).
3. **Select Checkpoint & Data:** Choose `tumor_model.pt` and the `tumor-detection` folder.
4. Click **Start Training**.
5. Open a second instance of the Edge Node (via terminal `npm start` in the `client` folder).
6. Set the Target Job ID to `1`, select the tumor data, and click **Start Training**.
7. *Watch the Gamma server terminal perfectly isolate and aggregate the weights on a rolling basis.*

### Step 7: View the Isolated Results
1. Return to your web browser (`http://localhost:3000`) and log in as an authorized client or ML Engineer.
2. Click **View Live Dashboard & Details** on the job card.
3. You will see the interactive Recharts plotting the exact accuracy, loss, and specific weight parameter updates dynamically saved to that specific Job ID, updated in real-time!

---

##  Comprehensive Testing Suite

To ensure the reliability, security, and mathematical accuracy of the platform, we implemented a multi-tiered automated testing strategy using `pytest` and `Jest`.

### 1. Backend API & Integration Testing (FastAPI / SQLite)
We utilized an in-memory SQLite database (`StaticPool`) and FastAPI's `TestClient` to test the orchestration API without impacting development data.
* **Authentication & RBAC:** Verified that JWT generation works and that strict Role-Based Access Control (RBAC) prevents unauthorized users from creating or modifying jobs.
* **Zero-Knowledge Privacy Integration:** Wrote end-to-end integration tests proving that if a new Client Operator attempts to view a completed job, the API dynamically scrubs the proprietary `final_weights` and `metrics` arrays until that specific user has contributed local data.

### 2. Machine Learning Unit Testing (FedAvg)
We wrote isolated mathematical unit tests for the core aggregation engine (`fedavg_mock.py`).
* **Flat Array Averaging:** Proved that the system accurately calculates weighted averages based on variable patient sample counts across different hospitals.
* **Structured PyTorch State Dictionaries:** Proved that the engine correctly extracts, averages, and reconstructs multi-layer nested tensors (weights and biases) while preserving the exact neural network architecture.
* **Edge-Case Handling:** Ensured the engine safely catches divide-by-zero errors if aggregation is triggered prematurely.

### 3. Frontend Component Testing (React Testing Library / Jest)
We isolated React components to ensure the user interface behaves predictably.
* **API Mocking:** Intercepted Axios calls to render the Dashboard purely on local state.
* **Event Simulation:** Programmatically verified that the "Download Edge App (.dmg/.exe)" buttons successfully trigger the correct OS-specific FastAPI download endpoints without crashing the browser router.
```
