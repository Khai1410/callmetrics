import ipaddress
import os
import re
import shutil
import socket
import uuid
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests
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

CONTENT_TYPE_EXT = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
}

MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024  # 300MB, matches nginx client_max_body_size
DOWNLOAD_TIMEOUT = (15, 120)  # (connect, read-per-chunk) seconds

HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
AUDIO_SRC_PARAM_NAMES = ("src", "file", "audio", "url", "path")
_AUDIO_TAG_RE = re.compile(r'<(?:audio|source)[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _is_html_content_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    return content_type.split(";")[0].strip().lower() in HTML_CONTENT_TYPES


def _resolve_audio_url(url: str) -> str:
    """Many internal call-recording portals hand out a *player page* URL
    (e.g. player.php?src=files/xxx.ogg) rather than a direct link to the
    audio file, so a plain download would just fetch HTML. Try to recover
    the real audio URL: first from a common query-param name, then — if
    that guess still points at an HTML page — by scanning the page for an
    <audio>/<source> tag."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in AUDIO_SRC_PARAM_NAMES:
        if qs.get(key):
            candidate = urljoin(url, qs[key][0])
            try:
                head = requests.head(candidate, timeout=DOWNLOAD_TIMEOUT, allow_redirects=True)
                if not _is_html_content_type(head.headers.get("Content-Type")):
                    return candidate
            except requests.RequestException:
                return candidate

    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        if _is_html_content_type(resp.headers.get("Content-Type")):
            match = _AUDIO_TAG_RE.search(resp.text)
            if match:
                return urljoin(url, match.group(1))
    except requests.RequestException:
        pass

    return url


def _guess_extension(url: str, content_type: Optional[str]) -> str:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in CONTENT_TYPE_EXT:
            return CONTENT_TYPE_EXT[ct]
    path_ext = os.path.splitext(urlparse(url).path)[1].lower()
    if path_ext in ALLOWED_EXTENSIONS:
        return path_ext
    return ".mp3"


def _assert_safe_url(url: str):
    """Basic SSRF guard: only http(s), and refuse hostnames that resolve to
    private/loopback/link-local addresses. This is a lightweight check, not a
    full SSRF defense — only meant for pasting trusted recording-portal links."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "URL phải bắt đầu bằng http:// hoặc https://")
    if not parsed.hostname:
        raise HTTPException(400, "URL không hợp lệ")
    try:
        addrs = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(400, f"Không phân giải được tên miền: {exc}") from exc
    for family, _, _, _, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(400, "URL trỏ tới địa chỉ mạng nội bộ, không được phép")


def _download_to_storage(url: str) -> tuple[str, Optional[str]]:
    resolved_url = _resolve_audio_url(url)
    if resolved_url != url:
        _assert_safe_url(resolved_url)

    with requests.get(resolved_url, stream=True, timeout=DOWNLOAD_TIMEOUT) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type")
        if _is_html_content_type(content_type):
            raise ValueError(
                "URL trả về một trang HTML, không phải file âm thanh. "
                "Đây có thể là link trang nghe online chứ không phải link file gốc — "
                "kiểm tra lại URL đã copy."
            )
        ext = _guess_extension(resolved_url, content_type)
        stored_name = f"{uuid.uuid4()}{ext}"
        dest_path = os.path.join(STORAGE_DIR, stored_name)
        total = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    f.close()
                    os.remove(dest_path)
                    raise ValueError("File ghi âm vượt quá giới hạn 300MB")
                f.write(chunk)
        if total == 0:
            os.remove(dest_path)
            raise ValueError("URL không trả về dữ liệu (file rỗng)")
        return dest_path, content_type


def _transcribe_record(db, record: "models.Record"):
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


def _run_transcription(record_id: str):
    db = SessionLocal()
    try:
        record = db.get(models.Record, record_id)
        if not record:
            return
        _transcribe_record(db, record)
    finally:
        db.close()


def _run_fetch_and_transcribe(record_id: str, url: str):
    db = SessionLocal()
    try:
        record = db.get(models.Record, record_id)
        if not record:
            return
        record.status = models.RecordStatus.FETCHING.value
        db.commit()
        try:
            dest_path, content_type = _download_to_storage(url)
        except Exception as exc:  # noqa: BLE001
            record.status = models.RecordStatus.FAILED.value
            record.error_message = f"Lỗi tải ghi âm từ URL: {exc}"
            db.commit()
            return

        record.storage_path = dest_path
        record.mime_type = content_type
        db.commit()

        _transcribe_record(db, record)
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


@router.post("/records/from-url", response_model=schemas.RecordOut)
def create_record_from_url(
    payload: schemas.RecordFromUrlCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    url = payload.url.strip()
    if not url:
        raise HTTPException(400, "URL không được để trống")
    _assert_safe_url(url)

    criteria_set = db.get(models.CriteriaSet, payload.criteria_set_id)
    if not criteria_set:
        raise HTTPException(404, "Criteria set không tồn tại")

    display_name = payload.filename or os.path.basename(urlparse(url).path) or "ghi-am-tu-url"

    record = models.Record(
        original_filename=display_name,
        storage_path="",
        mime_type=None,
        criteria_set_id=payload.criteria_set_id,
        uploaded_by=payload.uploaded_by,
        status=models.RecordStatus.FETCHING.value,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    background_tasks.add_task(_run_fetch_and_transcribe, record.id, url)

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
    if not record or not record.storage_path or not os.path.exists(record.storage_path):
        raise HTTPException(404, "File not found")
    return FileResponse(record.storage_path, media_type=record.mime_type or "application/octet-stream")


@router.delete("/records/{record_id}")
def delete_record(record_id: str, db: Session = Depends(get_db)):
    record = db.get(models.Record, record_id)
    if not record:
        raise HTTPException(404, "Record not found")
    if record.storage_path and os.path.exists(record.storage_path):
        os.remove(record.storage_path)
    db.delete(record)
    db.commit()
    return {"ok": True}
