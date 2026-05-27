from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="investigator") # e.g., admin, investigator, system

class AuditLog(Base):
    """
    Event Sourced Audit Trail. Every decision the LangGraph agents make is stored here 
    for immutable compliance logging.
    """
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, index=True, nullable=False)
    agent_name = Column(String, index=True, nullable=False) # e.g., "Supervisor", "Risk_Intel"
    action_type = Column(String, nullable=False) # e.g., "QUERY_GRAPH", "FINAL_VERDICT"
    details = Column(JSON, nullable=True) # Arbitrary JSON payload of the action
    timestamp = Column(DateTime, default=datetime.utcnow)

class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="PROCESSING") # PROCESSING, COMPLETED, FAILED
    fraud_score = Column(Float, nullable=True)
    verdict = Column(String, nullable=True)
    explanation = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
