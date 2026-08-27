import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import SessionLocal, get_db
from ..transcription import transcribe_file

router = APIRouter(prefix="/api", tags=["records"])

STORAGE_DIR = os.getenv("STORAGE_DIR", "/data/audio")
os.makedirs(STORAGE_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma"}


def _run_transcription(record_id: str):
    db = SessionLocal()
    try:
        record = db.get(models.Record, record_id)
        if not record:
            return
        record.status = models.RecordStatus.TRANSCRIBING.value
        db.commit()
        try:
            result = transcribe_file(record.storage_path)
            transcript = models.Transcript(
                record_id=record.id,
                text=result["text"],
                segments=result["segments"],
                language=result["language"],
            )
            record.duration_seconds = result.get("duration")
            record.status = models.RecordStatus.TRANSCRIBED.value
            db.add(transcript)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            record.status = models.RecordStatus.FAILED.value
            record.error_message = str(exc)
            db.commit()
    finally:
        db.close()


@router.post("/records", response_model=schemas.RecordOut)
def upload_record(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    criteria_set_id: str = Form(...),
    uploaded_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Định dạng file không hỗ trợ: {ext}")

    criteria_set = db.get(models.CriteriaSet, criteria_set_id)
    if not criteria_set:
        raise HTTPException(404, "Criteria set không tồn tại")

    stored_name = f"{uuid.uuid4()}{ext}"
    dest_path = os.path.join(STORAGE_DIR, stored_name)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    record = models.Record(
        original_filename=file.filename,
        storage_path=dest_path,
        mime_type=file.content_type,
        criteria_set_id=criteria_set_id,
        uploaded_by=uploaded_by,
        status=models.RecordStatus.UPLOADED.value,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    background_tasks.add_task(_run_transcription, record.id)

    return record


@router.get("/records", response_model=list[schemas.RecordOut])
def list_records(db: Session = Depends(get_db)):
    return db.query(models.Record).order_by(models.Record.created_at.desc()).all()


@router.get("/records/{record_id}", response_model=schemas.RecordDetailOut)
def get_record(record_id: str, db: Session = Depends(get_db)):
    record = db.get(models.Record, record_id)
    if not record:
        raise HTTPException(404, "Record not found")
    return record


@router.get("/records/{record_id}/audio")
def get_record_audio(record_id: str, db: Session = Depends(get_db)):
    record = db.get(models.Record, record_id)
    if not record or not os.path.exists(record.storage_path):
        raise HTTPException(404, "File not found")
    return FileResponse(record.storage_path, media_type=record.mime_type or "application/octet-stream")


@router.delete("/records/{record_id}")
def delete_record(record_id: str, db: Session = Depends(get_db)):
    record = db.get(models.Record, record_id)
    if not record:
        raise HTTPException(404, "Record not found")
    if os.path.exists(record.storage_path):
        os.remove(record.storage_path)
    db.delete(record)
    db.commit()
    return {"ok": True}
