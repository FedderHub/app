from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import engine
from app import models
from app.routers import auth, jobs

# Create all tables on startup (including new RoundMetric table)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FederHub Alpha API",
    description="Phase 3 – Beta Login Bridge + Gamma Metrics Integration",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Phase 3: Electron app uses file:// protocol which sends Origin: null
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(jobs.router)


# ── Health & root ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "FederHub Alpha API v3 is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
