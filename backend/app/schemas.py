from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ScoreOption(BaseModel):
    value: float
    label: str


class CriterionBase(BaseModel):
    stt: int = 0
    name: str
    description: Optional[str] = None
    weight: Optional[float] = None
    include_in_total: bool = True
    selection_type: str = "single"
    score_options: list[ScoreOption] = []
    check_type: str = "manual"
    check_config: Optional[dict[str, Any]] = None
    is_active: bool = True


class CriterionCreate(CriterionBase):
    pass


class CriterionUpdate(BaseModel):
    stt: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    include_in_total: Optional[bool] = None
    selection_type: Optional[str] = None
    score_options: Optional[list[ScoreOption]] = None
    check_type: Optional[str] = None
    check_config: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class CriterionOut(CriterionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    criteria_set_id: str


class Threshold(BaseModel):
    min: float
    label: str


class CriteriaSetBase(BaseModel):
    code: str
    name: str
    max_score: float = 5
    thresholds: list[Threshold] = []
    call_content_types: list[str] = []
    failed_point_tags: list[str] = []


class CriteriaSetCreate(CriteriaSetBase):
    pass


class CriteriaSetUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    max_score: Optional[float] = None
    thresholds: Optional[list[Threshold]] = None
    call_content_types: Optional[list[str]] = None
    failed_point_tags: Optional[list[str]] = None


class CriteriaSetOut(CriteriaSetBase):
    model_config = ConfigDict(from_attributes=True)
    id: str


class CriteriaSetWithCriteria(CriteriaSetOut):
    criteria: list[CriterionOut] = []


class RecordFromUrlCreate(BaseModel):
    url: str
    criteria_set_id: str
    uploaded_by: Optional[str] = None
    filename: Optional[str] = None


class RecordUpdate(BaseModel):
    criteria_set_id: Optional[str] = None
    uploaded_by: Optional[str] = None


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: str
    duration_seconds: Optional[float] = None
    criteria_set_id: str
    uploaded_by: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime


class TranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    text: Optional[str] = None
    segments: Optional[list[dict[str, Any]]] = None
    language: Optional[str] = None


class RecordDetailOut(RecordOut):
    transcript: Optional[TranscriptOut] = None
    criteria_set: CriteriaSetOut


class ScoreItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    criterion_id: str
    auto_score: Optional[float] = None
    auto_evidence: Optional[str] = None
    final_score: Optional[float] = None
    note: Optional[str] = None


class ScoreItemUpdate(BaseModel):
    final_score: Optional[float] = None
    note: Optional[str] = None


class ScoringSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    record_id: str
    criteria_set_id: str
    scorer_name: Optional[str] = None
    call_content_type: Optional[str] = None
    failed_point_tags: list[str] = []
    overall_comment: Optional[str] = None
    status: str
    total_score: Optional[float] = None
    classification: Optional[str] = None
    created_at: datetime
    items: list[ScoreItemOut] = []


class ScoringSessionCreate(BaseModel):
    scorer_name: Optional[str] = None


class ScoringSessionUpdate(BaseModel):
    scorer_name: Optional[str] = None
    call_content_type: Optional[str] = None
    failed_point_tags: Optional[list[str]] = None
    overall_comment: Optional[str] = None
