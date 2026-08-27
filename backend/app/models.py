import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class RecordStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    FAILED = "failed"


class SessionStatus(str, enum.Enum):
    DRAFT = "draft"
    COMPLETED = "completed"


class CriteriaSet(Base):
    __tablename__ = "criteria_sets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    max_score = Column(Float, nullable=False, default=5)
    thresholds = Column(JSON, nullable=False, default=list)
    call_content_types = Column(JSON, nullable=False, default=list)
    failed_point_tags = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    criteria = relationship(
        "Criterion",
        back_populates="criteria_set",
        cascade="all, delete-orphan",
        order_by="Criterion.stt",
    )


class Criterion(Base):
    __tablename__ = "criteria"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    criteria_set_id = Column(UUID(as_uuid=False), ForeignKey("criteria_sets.id"), nullable=False)
    stt = Column(Integer, nullable=False, default=0)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    weight = Column(Float, nullable=True)
    include_in_total = Column(Boolean, nullable=False, default=True)
    selection_type = Column(String, nullable=False, default="single")
    score_options = Column(JSON, nullable=False, default=list)
    check_type = Column(String, nullable=False, default="manual")
    check_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    criteria_set = relationship("CriteriaSet", back_populates="criteria")


class Record(Base):
    __tablename__ = "records"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    criteria_set_id = Column(UUID(as_uuid=False), ForeignKey("criteria_sets.id"), nullable=False)
    uploaded_by = Column(String, nullable=True)
    status = Column(String, nullable=False, default=RecordStatus.UPLOADED.value)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    criteria_set = relationship("CriteriaSet")
    transcript = relationship("Transcript", back_populates="record", uselist=False, cascade="all, delete-orphan")
    scoring_sessions = relationship("ScoringSession", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    record_id = Column(UUID(as_uuid=False), ForeignKey("records.id"), unique=True, nullable=False)
    text = Column(Text, nullable=True)
    segments = Column(JSON, nullable=True)
    language = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    record = relationship("Record", back_populates="transcript")


class ScoringSession(Base):
    __tablename__ = "scoring_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    record_id = Column(UUID(as_uuid=False), ForeignKey("records.id"), nullable=False)
    criteria_set_id = Column(UUID(as_uuid=False), ForeignKey("criteria_sets.id"), nullable=False)
    scorer_name = Column(String, nullable=True)
    call_content_type = Column(String, nullable=True)
    failed_point_tags = Column(JSON, nullable=False, default=list)
    overall_comment = Column(Text, nullable=True)
    status = Column(String, nullable=False, default=SessionStatus.DRAFT.value)
    total_score = Column(Float, nullable=True)
    classification = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    record = relationship("Record")
    criteria_set = relationship("CriteriaSet")
    items = relationship("ScoreItem", back_populates="session", cascade="all, delete-orphan")


class ScoreItem(Base):
    __tablename__ = "score_items"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("scoring_sessions.id"), nullable=False)
    criterion_id = Column(UUID(as_uuid=False), ForeignKey("criteria.id"), nullable=False)
    auto_score = Column(Float, nullable=True)
    auto_evidence = Column(Text, nullable=True)
    final_score = Column(Float, nullable=True)
    note = Column(Text, nullable=True)

    session = relationship("ScoringSession", back_populates="items")
    criterion = relationship("Criterion")
