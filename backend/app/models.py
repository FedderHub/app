from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
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
    role = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class JobConfiguration(Base):
    __tablename__ = "job_configurations"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)