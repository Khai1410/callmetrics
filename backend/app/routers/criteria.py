from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api", tags=["criteria"])


def _set_or_404(db: Session, set_id: str) -> models.CriteriaSet:
    obj = db.get(models.CriteriaSet, set_id)
    if not obj:
        raise HTTPException(404, "Criteria set not found")
    return obj


def _criterion_or_404(db: Session, criterion_id: str) -> models.Criterion:
    obj = db.get(models.Criterion, criterion_id)
    if not obj:
        raise HTTPException(404, "Criterion not found")
    return obj


@router.get("/criteria-sets", response_model=list[schemas.CriteriaSetOut])
def list_criteria_sets(db: Session = Depends(get_db)):
    return db.query(models.CriteriaSet).order_by(models.CriteriaSet.name).all()


@router.post("/criteria-sets", response_model=schemas.CriteriaSetOut)
def create_criteria_set(payload: schemas.CriteriaSetCreate, db: Session = Depends(get_db)):
    existing = db.query(models.CriteriaSet).filter_by(code=payload.code).first()
    if existing:
        raise HTTPException(400, "Code đã tồn tại")
    obj = models.CriteriaSet(**payload.model_dump(mode="json"))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/criteria-sets/{set_id}", response_model=schemas.CriteriaSetWithCriteria)
def get_criteria_set(set_id: str, db: Session = Depends(get_db)):
    return _set_or_404(db, set_id)


@router.patch("/criteria-sets/{set_id}", response_model=schemas.CriteriaSetOut)
def update_criteria_set(set_id: str, payload: schemas.CriteriaSetUpdate, db: Session = Depends(get_db)):
    obj = _set_or_404(db, set_id)
    for k, v in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/criteria-sets/{set_id}")
def delete_criteria_set(set_id: str, db: Session = Depends(get_db)):
    obj = _set_or_404(db, set_id)
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/criteria-sets/{set_id}/criteria", response_model=schemas.CriterionOut)
def add_criterion(set_id: str, payload: schemas.CriterionCreate, db: Session = Depends(get_db)):
    _set_or_404(db, set_id)
    data = payload.model_dump(mode="json")
    obj = models.Criterion(criteria_set_id=set_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/criteria/{criterion_id}", response_model=schemas.CriterionOut)
def update_criterion(criterion_id: str, payload: schemas.CriterionUpdate, db: Session = Depends(get_db)):
    obj = _criterion_or_404(db, criterion_id)
    for k, v in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/criteria/{criterion_id}")
def delete_criterion(criterion_id: str, db: Session = Depends(get_db)):
    obj = _criterion_or_404(db, criterion_id)
    db.delete(obj)
    db.commit()
    return {"ok": True}
