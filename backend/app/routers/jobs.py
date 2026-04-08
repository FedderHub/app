from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import models
from app.schemas import JobCreate, JobOut
from app.auth import get_db, get_current_user, require_role

router = APIRouter(prefix="/jobs", tags=["Jobs"])


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
    return job


@router.get("/", response_model=List[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all jobs. Any authenticated user can view."""
    return db.query(models.JobConfiguration).order_by(
        models.JobConfiguration.created_at.desc()
    ).all()


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
    return job


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
    return job
