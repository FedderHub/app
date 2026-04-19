# db_connector.py
# ================
# FederHub - Team Gamma | Phase 3
# --------------------------------
# Connects Gamma's aggregation engine to Alpha's PostgreSQL database.
# Provides methods to:
#   1. Fetch job configuration (round_count, local_epochs, status)
#   2. Update job status (draft → running → completed → failed)
#   3. Record per-round metrics (accuracy, loss, weight snapshot)
#   4. Retrieve round metrics for a job
#
# Uses SQLAlchemy (matching Alpha's stack) with DATABASE_URL from env.

import json
import os
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, JobConfiguration, RoundMetric


def _get_database_url():
    """Read DATABASE_URL from environment, with a sensible fallback for dev."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise EnvironmentError(
            "DATABASE_URL is not set. Set it in your environment or .env file.\n"
            "Example: DATABASE_URL=postgresql://user:pass@host:5432/federhub"
        )
    return url


def create_db_session(database_url: str = None):
    """
    Create a SQLAlchemy session. If no URL is provided, reads from env.

    Returns:
        (Session, engine) tuple.
    """
    url = database_url or _get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    # Ensure Gamma's tables exist (RoundMetric) without affecting Alpha's
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session(), engine


# ── Job Configuration (read from Alpha's table) ─────────────────────────────

def fetch_job_config(session, job_id: int) -> dict:
    """
    Fetch a job's configuration from Alpha's job_configurations table.

    Args:
        session: SQLAlchemy session.
        job_id: The job ID to look up.

    Returns:
        dict with job_name, round_count, local_epochs, status.

    Raises:
        ValueError: If the job is not found.
    """
    job = session.query(JobConfiguration).filter(
        JobConfiguration.id == job_id
    ).first()

    if not job:
        raise ValueError(f"Job with id={job_id} not found in the database.")

    return {
        "id": job.id,
        "job_name": job.job_name,
        "round_count": job.round_count,
        "local_epochs": job.local_epochs,
        "status": job.status,
        "created_at": job.created_at,
    }


# ── Job Status (write to Alpha's table) ─────────────────────────────────────

VALID_STATUSES = {"draft", "scheduled", "running", "completed", "failed"}


def update_job_status(session, job_id: int, new_status: str) -> dict:
    """
    Update a job's status in Alpha's database.

    Args:
        session: SQLAlchemy session.
        job_id: The job ID to update.
        new_status: One of: draft, scheduled, running, completed, failed.

    Returns:
        dict with the updated job info.

    Raises:
        ValueError: If the job is not found or the status is invalid.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{new_status}'. Must be one of: {VALID_STATUSES}"
        )

    job = session.query(JobConfiguration).filter(
        JobConfiguration.id == job_id
    ).first()

    if not job:
        raise ValueError(f"Job with id={job_id} not found in the database.")

    job.status = new_status
    session.commit()
    session.refresh(job)

    return {
        "id": job.id,
        "job_name": job.job_name,
        "status": job.status,
    }


# ── Round Metrics (Gamma-owned table) ────────────────────────────────────────

def record_round_metric(
    session,
    job_id: int,
    round_number: int,
    accuracy: float = None,
    loss: float = None,
    num_clients: int = None,
    total_samples: int = None,
    global_weights_snapshot: dict = None,
) -> RoundMetric:
    """
    Record metrics for a completed federated round.

    Args:
        session: SQLAlchemy session.
        job_id: The job this round belongs to.
        round_number: Which round (1-indexed).
        accuracy: Optional aggregated accuracy.
        loss: Optional aggregated loss.
        num_clients: Number of clients that participated.
        total_samples: Total samples across all clients.
        global_weights_snapshot: Optional dict summary of global weights.

    Returns:
        The created RoundMetric record.
    """
    snapshot_json = None
    if global_weights_snapshot is not None:
        snapshot_json = json.dumps(global_weights_snapshot)

    metric = RoundMetric(
        job_id=job_id,
        round_number=round_number,
        accuracy=accuracy,
        loss=loss,
        num_clients=num_clients,
        total_samples=total_samples,
        global_weights_snapshot=snapshot_json,
        completed_at=datetime.utcnow(),
    )
    session.add(metric)
    session.commit()
    session.refresh(metric)

    return metric


def get_round_metrics(session, job_id: int) -> list:
    """
    Retrieve all round metrics for a given job, ordered by round number.

    Args:
        session: SQLAlchemy session.
        job_id: The job ID.

    Returns:
        List of dicts with round_number, accuracy, loss, etc.
    """
    metrics = (
        session.query(RoundMetric)
        .filter(RoundMetric.job_id == job_id)
        .order_by(RoundMetric.round_number)
        .all()
    )

    return [
        {
            "id": m.id,
            "job_id": m.job_id,
            "round_number": m.round_number,
            "accuracy": m.accuracy,
            "loss": m.loss,
            "num_clients": m.num_clients,
            "total_samples": m.total_samples,
            "global_weights_snapshot": (
                json.loads(m.global_weights_snapshot)
                if m.global_weights_snapshot
                else None
            ),
            "completed_at": m.completed_at,
        }
        for m in metrics
    ]
