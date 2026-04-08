from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import engine
from app import models
from app.routers import auth, jobs

# Create all tables on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FederHub Alpha API",
    description="Phase 2 – JWT Auth + Job Management",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    return {"message": "FederHub Alpha API v2 is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
