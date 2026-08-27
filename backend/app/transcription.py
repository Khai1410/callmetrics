import os
import threading

_model = None
_model_lock = threading.Lock()

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# Biases the model's vocabulary/spelling toward correctly-accented Vietnamese
# customer-service phrasing, which measurably reduces diacritic/spelling
# errors on call-center audio. Override via env var to add company-specific
# terms (product names, brand names, etc.) without a code change.
DEFAULT_INITIAL_PROMPT = (
    "Cuộc gọi chăm sóc khách hàng và tư vấn bán hàng. Xin chào anh, chào chị, "
    "em là tổng đài viên, xin phép hỗ trợ mình về sản phẩm, chương trình khuyến mãi, "
    "khách hàng thân thiết, thời hạn sử dụng, cảm ơn anh chị đã tin tưởng, tổng đài, hotline."
)
WHISPER_INITIAL_PROMPT = os.getenv("WHISPER_INITIAL_PROMPT") or DEFAULT_INITIAL_PROMPT


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel

                _model = WhisperModel(
                    WHISPER_MODEL_SIZE,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE_TYPE,
                )
    return _model


def transcribe_file(file_path: str) -> dict:
    """Runs local speech-to-text (no external AI/API calls). Returns transcript
    text, per-segment timings, detected language and audio duration."""
    model = get_model()
    segments_iter, info = model.transcribe(
        file_path,
        language="vi",
        vad_filter=True,
        beam_size=5,
        initial_prompt=WHISPER_INITIAL_PROMPT or None,
    )

    segments = []
    full_text_parts = []
    for seg in segments_iter:
        segments.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()})
        full_text_parts.append(seg.text.strip())

    return {
        "text": " ".join(full_text_parts).strip(),
        "segments": segments,
        "language": info.language,
        "duration": info.duration,
    }
