from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..scoring_engine import auto_score_criterion, classify, compute_total

router = APIRouter(prefix="/api", tags=["scoring"])


@router.post("/records/{record_id}/scoring-session", response_model=schemas.ScoringSessionOut)
def create_scoring_session(record_id: str, payload: schemas.ScoringSessionCreate, db: Session = Depends(get_db)):
    record = db.get(models.Record, record_id)
    if not record:
        raise HTTPException(404, "Record not found")

    session = models.ScoringSession(
        record_id=record.id,
        criteria_set_id=record.criteria_set_id,
        scorer_name=payload.scorer_name,
        status=models.SessionStatus.DRAFT.value,
    )
    db.add(session)
    db.flush()

    transcript_text = record.transcript.text if record.transcript else ""
    criteria = (
        db.query(models.Criterion)
        .filter_by(criteria_set_id=record.criteria_set_id, is_active=True)
        .order_by(models.Criterion.stt)
        .all()
    )
    for criterion in criteria:
        auto_score, evidence = auto_score_criterion(criterion, transcript_text)
        item = models.ScoreItem(
            session_id=session.id,
            criterion_id=criterion.id,
            auto_score=auto_score,
            auto_evidence=evidence,
            final_score=auto_score,
        )
        db.add(item)

    db.commit()
    db.refresh(session)
    return session


@router.get("/scoring-sessions", response_model=list[schemas.ScoringSessionOut])
def list_scoring_sessions(db: Session = Depends(get_db)):
    return db.query(models.ScoringSession).order_by(models.ScoringSession.created_at.desc()).all()


@router.get("/scoring-sessions/{session_id}", response_model=schemas.ScoringSessionOut)
def get_scoring_session(session_id: str, db: Session = Depends(get_db)):
    session = db.get(models.ScoringSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.patch("/scoring-sessions/{session_id}", response_model=schemas.ScoringSessionOut)
def update_scoring_session(session_id: str, payload: schemas.ScoringSessionUpdate, db: Session = Depends(get_db)):
    session = db.get(models.ScoringSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    for k, v in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(session, k, v)
    db.commit()
    db.refresh(session)
    return session


@router.patch("/scoring-sessions/{session_id}/items/{criterion_id}", response_model=schemas.ScoreItemOut)
def update_score_item(session_id: str, criterion_id: str, payload: schemas.ScoreItemUpdate, db: Session = Depends(get_db)):
    item = (
        db.query(models.ScoreItem)
        .filter_by(session_id=session_id, criterion_id=criterion_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Score item not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.post("/scoring-sessions/{session_id}/complete", response_model=schemas.ScoringSessionOut)
def complete_scoring_session(session_id: str, db: Session = Depends(get_db)):
    session = db.get(models.ScoringSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    criteria_set = db.get(models.CriteriaSet, session.criteria_set_id)
    criteria = {c.id: c for c in criteria_set.criteria}
    final_scores = {item.criterion_id: item.final_score for item in session.items if item.final_score is not None}

    total, missing = compute_total(list(criteria.values()), final_scores)
    if missing:
        missing_names = [criteria[cid].name for cid in missing if cid in criteria]
        raise HTTPException(400, f"Còn tiêu chí chưa được chấm điểm: {', '.join(missing_names)}")

    session.total_score = total
    session.classification = classify(total, criteria_set.thresholds)
    session.status = models.SessionStatus.COMPLETED.value
    db.commit()
    db.refresh(session)
    return session
