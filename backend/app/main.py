from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.db import engine, SessionLocal
from app import models

app = FastAPI(title="FederHub Alpha API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "FederHub Alpha backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/organizations")
def get_organizations():
    db: Session = SessionLocal()
    try:
        orgs = db.query(models.Organization).all()
        return [
            {
                "id": org.id,
                "name": org.name,
                "created_at": org.created_at
            }
            for org in orgs
        ]
    finally:
        db.close()

@app.get("/users")
def get_users():
    return [
        {"id": 1, "email": "admin@federhub.com", "role": "platform_admin", "status": "active"},
        {"id": 2, "email": "ml@federhub.com", "role": "ml_engineer", "status": "active"},
    ]

@app.get("/jobs")
def get_jobs():
    return [
        {"id": 1, "job_name": "Round-Test-Job", "status": "draft"},
    ]