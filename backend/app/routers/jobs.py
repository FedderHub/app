from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import models
from app.config import REDIS_URL
from app.schemas import JobCreate, JobOut, JobStartResponse, RoundMetricOut
from app.auth import get_db, get_current_user, require_role

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def job_to_out(job: models.JobConfiguration, creator_email: str | None = None) -> JobOut:
    return JobOut(
        id=job.id,
        job_name=job.job_name,
        round_count=job.round_count,
        local_epochs=job.local_epochs,
        status=job.status,
        created_by=job.created_by,
        creator_email=creator_email,
        created_at=job.created_at,
    )


@router.post("/", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_role("platform_admin", "ml_engineer")
    ),
):
    """Create a new federated training job. Requires ml_engineer or platform_admin role."""
    job = models.JobConfiguration(
        job_name=payload.job_name,
        round_count=payload.round_count,
        local_epochs=payload.local_epochs,
        status="draft",
        created_by=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job_to_out(job, current_user.email)


@router.get("/", response_model=List[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all jobs. Any authenticated user can view."""
    rows = (
        db.query(models.JobConfiguration, models.User.email)
        .outerjoin(models.User, models.JobConfiguration.created_by == models.User.id)
        .order_by(models.JobConfiguration.created_at.desc())
        .all()
    )
    return [job_to_out(job, creator_email) for job, creator_email in rows]


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get a single job by ID."""
    job = db.query(models.JobConfiguration).filter(
        models.JobConfiguration.id == job_id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    creator_email = None
    if job.created_by:
        creator = db.query(models.User).filter(models.User.id == job.created_by).first()
        creator_email = creator.email if creator else None
    return job_to_out(job, creator_email)


@router.post("/{job_id}/start", response_model=JobStartResponse)
def start_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_role("platform_admin", "ml_engineer")
    ),
):
    """Schedule a federated job for Gamma's orchestration worker."""
    job = db.query(models.JobConfiguration).filter(
        models.JobConfiguration.id == job_id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = "scheduled"
    db.commit()
    db.refresh(job)

    try:
        from celery import Celery

        celery_app = Celery("federhub_alpha", broker=REDIS_URL, backend=REDIS_URL)
        task = celery_app.send_task("federhub.run_federation_job", args=[job_id])
        return JobStartResponse(
            job_id=job.id,
            status=job.status,
            task_id=task.id,
            message="Job scheduled. Start Gamma's Celery worker and gRPC aggregator to process rounds.",
        )
    except Exception as exc:
        return JobStartResponse(
            job_id=job.id,
            status=job.status,
            task_id=None,
            message=f"Job marked scheduled, but the Celery task could not be queued: {exc}",
        )


@router.get("/{job_id}/metrics", response_model=List[RoundMetricOut])
def get_job_metrics(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return per-round metrics written by Gamma's aggregation engine."""
    job = db.query(models.JobConfiguration).filter(
        models.JobConfiguration.id == job_id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return db.query(models.RoundMetric).filter(
        models.RoundMetric.job_id == job_id
    ).order_by(models.RoundMetric.round_number.asc()).all()


@router.patch("/{job_id}/status", response_model=JobOut)
def update_job_status(
    job_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_role("platform_admin", "ml_engineer")
    ),
):
    """Update a job's status (draft → scheduled → running → completed)."""
    allowed = {"draft", "scheduled", "running", "completed", "failed"}
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Choose from: {allowed}",
        )
    job = db.query(models.JobConfiguration).filter(
        models.JobConfiguration.id == job_id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    job.status = new_status
    db.commit()
    db.refresh(job)
    creator_email = None
    if job.created_by:
        creator = db.query(models.User).filter(models.User.id == job.created_by).first()
        creator_email = creator.email if creator else None
    return job_to_out(job, creator_email)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_role("platform_admin", "ml_engineer")
    ),
):
    """Delete a training job and its associated round metrics."""
    job = db.query(models.JobConfiguration).filter(
        models.JobConfiguration.id == job_id
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    db.query(models.RoundMetric).filter(models.RoundMetric.job_id == job_id).delete()
    db.delete(job)
    db.commit()
    return None
