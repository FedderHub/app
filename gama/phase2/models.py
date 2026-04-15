# models.py
# =========
# FederHub - Team Gamma | Phase 3
# --------------------------------
# Defines the RoundMetric table that Gamma writes to after each
# federated aggregation round. This table lives in Alpha's PostgreSQL
# database alongside their existing tables (organizations, users,
# job_configurations).
#
# Gamma creates this table on startup via Base.metadata.create_all().

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ── Mirror of Alpha's table (read-only from Gamma's perspective) ─────────────

class JobConfiguration(Base):
    """
    Mirror of Alpha's job_configurations table.

    Gamma reads round_count, local_epochs, and status from this table
    to drive the federated training loop. Gamma also updates the status
    field as rounds progress.
    """
    __tablename__ = "job_configurations"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, nullable=False)
    round_count = Column(Integer, nullable=False, default=5)
    local_epochs = Column(Integer, nullable=False, default=3)
    status = Column(String, nullable=False, default="draft")
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Gamma-owned table ────────────────────────────────────────────────────────

class RoundMetric(Base):
    """
    Per-round metrics recorded by Gamma's aggregation engine.

    After each FedAvg round completes, the aggregation server writes
    accuracy, loss, and a snapshot of the global weight summary to
    this table. Alpha's React dashboard can query this to show
    real-time training progress.
    """
    __tablename__ = "round_metrics"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_configurations.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    accuracy = Column(Float, nullable=True)
    loss = Column(Float, nullable=True)
    num_clients = Column(Integer, nullable=True)
    total_samples = Column(Integer, nullable=True)
    global_weights_snapshot = Column(Text, nullable=True)  # JSON summary
    completed_at = Column(DateTime, default=datetime.utcnow)
