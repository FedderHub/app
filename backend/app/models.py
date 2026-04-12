from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from datetime import datetime
from app.db import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=True)   # Phase 3: Beta Electron login
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="ml_engineer")
    status = Column(String, nullable=False, default="active")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class JobConfiguration(Base):
    __tablename__ = "job_configurations"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, nullable=False)
    round_count = Column(Integer, nullable=False, default=5)
    local_epochs = Column(Integer, nullable=False, default=3)
    status = Column(String, nullable=False, default="draft")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RoundMetric(Base):
    """Stores per-round aggregation results posted by Team Gamma's gRPC engine."""
    __tablename__ = "round_metrics"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_configurations.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    global_accuracy = Column(Float, nullable=False)
    num_clients = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
