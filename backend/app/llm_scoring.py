"""AI-based scoring: sends the call transcript plus the criteria rubric to an
LLM and asks it to score every criterion in one pass, so QA can review and
copy the result into the company portal instead of scoring by hand.

Two providers, picked by LLM_PROVIDER:
- "anthropic" (default): Claude via the Anthropic API, needs ANTHROPIC_API_KEY.
- "ollama": a local model served by Ollama (no API cost), see OLLAMA_* vars.

If the provider is not configured, or the call fails for any reason, callers
should fall back to the rule-based scoring_engine so the app stays usable.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
# Ollama's default context window (a few thousand tokens) silently truncates
# a long transcript + rubric, so it must be raised explicitly.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "16384"))
# CPU-only inference of a 7B model can take several minutes per call.
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "900"))

SYSTEM_PROMPT = (
    "Bạn là một chuyên gia QA (Quality Assurance) giàu kinh nghiệm trong lĩnh vực "
    "chăm sóc khách hàng / bán hàng qua điện thoại tại Việt Nam. Nhiệm vụ của bạn là "
    "nghe (đọc transcript) một cuộc gọi và chấm điểm khách quan, nghiêm túc theo đúng "
    "khung tiêu chí được cung cấp.\n\n"
    "Quy tắc bắt buộc:\n"
    "- Chỉ căn cứ vào nội dung xuất hiện trong transcript, không suy diễn hay bịa thông tin.\n"
    "- Với mỗi tiêu chí, chỉ được chọn một giá trị điểm NẰM TRONG danh sách score_options "
    "được cung cấp cho tiêu chí đó — không tự tạo giá trị điểm mới.\n"
    "- Nếu transcript không đủ căn cứ để đạt điểm cao, chọn mức điểm thấp hơn tương ứng, "
    "đừng chấm rộng tay.\n"
    "- Trích một đoạn ngắn (evidence) từ transcript làm bằng chứng cho điểm đã chọn; "
    "nếu tiêu chí không được thực hiện, ghi rõ ràng là không tìm thấy trong transcript.\n"
    "- Lưu ý transcript được chuyển tự động từ giọng nói (speech-to-text) nên có thể có "
    "lỗi chính tả/dấu câu nhỏ — đừng trừ điểm chỉ vì lỗi chính tả rõ ràng là do STT."
)


def _nearest_valid_score(value: float, options: list[dict[str, Any]]) -> float:
    valid = [float(o["value"]) for o in options]
    if not valid:
        return value
    return min(valid, key=lambda v: abs(v - value))


def _build_schema(
    criterion_ids: list[str], call_content_types: list[str], failed_point_tags: list[str]
) -> dict[str, Any]:
    call_type_schema: dict[str, Any] = {"type": "string"}
    if call_content_types:
        call_type_schema = {"type": "string", "enum": [*call_content_types, ""]}

    tag_item_schema: dict[str, Any] = {"type": "string"}
    if failed_point_tags:
        tag_item_schema = {"type": "string", "enum": failed_point_tags}

    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        # Small local models tend to mangle long UUIDs when copying them.
                        "criterion_id": {"type": "string", "enum": criterion_ids},
                        "score": {"type": "number"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["criterion_id", "score", "evidence"],
                    "additionalProperties": False,
                },
            },
            "call_content_type": call_type_schema,
            "failed_point_tags": {"type": "array", "items": tag_item_schema},
            "overall_comment": {"type": "string"},
        },
        "required": ["items", "call_content_type", "failed_point_tags", "overall_comment"],
        "additionalProperties": False,
    }


def is_configured() -> bool:
    if LLM_PROVIDER == "ollama":
        return bool(OLLAMA_BASE_URL and OLLAMA_MODEL)
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _call_anthropic(user_content: str, schema: dict[str, Any]) -> Optional[str]:
    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.APIStatusError as exc:
        logger.error("AI scoring failed (API status %s): %s", exc.status_code, exc.message)
        return None
    except anthropic.APIConnectionError as exc:
        logger.error("AI scoring failed (connection error): %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("AI scoring failed (unexpected error): %s", exc)
        return None

    if response.stop_reason == "refusal":
        logger.warning("AI scoring refused by the model")
        return None

    return next((b.text for b in response.content if b.type == "text"), None)


def _call_ollama(user_content: str, schema: dict[str, Any]) -> Optional[str]:
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                # Ollama constrains decoding to this JSON schema.
                "format": schema,
                "stream": False,
                "options": {"temperature": 0, "num_ctx": OLLAMA_NUM_CTX},
            },
            timeout=(10, OLLAMA_TIMEOUT),
        )
    except requests.RequestException as exc:
        logger.error("AI scoring failed (Ollama at %s unreachable): %s", OLLAMA_BASE_URL, exc)
        return None

    if resp.status_code != 200:
        # 404 here usually means the model has not been pulled yet.
        logger.error("AI scoring failed (Ollama status %s): %s", resp.status_code, resp.text[:500])
        return None

    data = resp.json()
    if data.get("done_reason") == "length":
        logger.warning("Ollama output hit the length limit, JSON may be truncated")
    return (data.get("message") or {}).get("content")


def score_with_ai(
    criteria: list,
    transcript_text: str,
    call_type_name: str,
    call_content_types: list[str],
    failed_point_tags: list[str],
) -> Optional[dict[str, Any]]:
    """Returns {"items": {criterion_id: {"score": float, "evidence": str}},
    "call_content_type": str, "failed_point_tags": list[str], "overall_comment": str}
    or None if AI scoring is unavailable/failed (caller should fall back)."""

    if not is_configured():
        return None
    if not transcript_text or not transcript_text.strip():
        return None

    criteria_payload = [
        {
            "criterion_id": c.id,
            "name": c.name,
            "rubric": c.description or "",
            "score_options": [o["value"] if isinstance(o, dict) else o.value for o in c.score_options],
        }
        for c in criteria
    ]

    user_content = (
        f"Loại cuộc gọi: {call_type_name}\n\n"
        "Transcript cuộc gọi (chuyển tự động từ giọng nói):\n"
        "<transcript>\n"
        f"{transcript_text.strip()}\n"
        "</transcript>\n\n"
        "Khung tiêu chí cần chấm (JSON), mỗi tiêu chí có rubric mô tả các mốc điểm:\n"
        "<criteria>\n"
        f"{json.dumps(criteria_payload, ensure_ascii=False, indent=2)}\n"
        "</criteria>\n\n"
        "Hãy chấm từng tiêu chí trong danh sách trên. Nếu có danh sách phân loại nội dung "
        "cuộc gọi hoặc các điểm không đạt bên dưới, hãy chọn giá trị phù hợp nhất "
        "(để mảng rỗng cho failed_point_tags nếu cuộc gọi không có lỗi nào đáng ghi nhận, "
        "hoặc để call_content_type là chuỗi rỗng nếu không có danh sách phù hợp):\n"
        f"call_content_types khả dụng: {json.dumps(call_content_types, ensure_ascii=False)}\n"
        f"failed_point_tags khả dụng: {json.dumps(failed_point_tags, ensure_ascii=False)}\n\n"
        "Cuối cùng viết overall_comment ngắn gọn (2-4 câu, tiếng Việt) tổng kết chất lượng "
        "cuộc gọi, phù hợp để copy thẳng vào báo cáo QA."
    )

    schema = _build_schema([c.id for c in criteria], call_content_types, failed_point_tags)

    if LLM_PROVIDER == "ollama":
        text = _call_ollama(user_content, schema)
    else:
        text = _call_anthropic(user_content, schema)
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.error("AI scoring returned invalid JSON: %s", text[:500])
        return None

    criteria_by_id = {c.id: c for c in criteria}
    items: dict[str, dict[str, Any]] = {}
    for item in parsed.get("items", []):
        cid = item.get("criterion_id")
        criterion = criteria_by_id.get(cid)
        if not criterion:
            continue
        score = _nearest_valid_score(float(item.get("score", 0)), criterion.score_options)
        items[cid] = {"score": score, "evidence": item.get("evidence", "")}

    return {
        "items": items,
        "call_content_type": parsed.get("call_content_type") or None,
        "failed_point_tags": [t for t in parsed.get("failed_point_tags", []) if t],
        "overall_comment": parsed.get("overall_comment") or None,
    }
