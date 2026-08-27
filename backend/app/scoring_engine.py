"""Rule-based (no-AI) auto-scoring: matches transcript text against configured
keyword groups for criteria that opt into check_type == "keyword". Every other
criterion is left for the QA to score manually after reading the transcript.
"""
from __future__ import annotations

import unicodedata
from typing import Any


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFC", text)
    return text


def evaluate_keyword_criterion(transcript_text: str, check_config: dict[str, Any]) -> tuple[float | None, str]:
    """Returns (auto_score, evidence_text)."""
    if not transcript_text:
        return None, "Chưa có transcript để kiểm tra."

    haystack = _normalize(transcript_text)
    groups = check_config.get("groups", [])
    score_full = check_config.get("score_full")
    score_partial = check_config.get("score_partial")
    score_none = check_config.get("score_none")

    matched_groups: list[str] = []
    missing_required: list[str] = []
    evidence_snippets: list[str] = []

    for group in groups:
        keywords = [_normalize(k) for k in group.get("keywords", [])]
        hit = None
        for kw in keywords:
            idx = haystack.find(kw)
            if idx != -1:
                hit = kw
                start = max(0, idx - 20)
                end = min(len(haystack), idx + len(kw) + 20)
                evidence_snippets.append(f'...{transcript_text[start:end].strip()}...')
                break
        if hit:
            matched_groups.append(group.get("name", "?"))
        elif group.get("required"):
            missing_required.append(group.get("name", "?"))

    required_groups = [g for g in groups if g.get("required")]
    required_matched = len(required_groups) - len(missing_required)

    if required_groups and not missing_required:
        score = score_full
        summary = "Đạt đủ các yếu tố bắt buộc: " + ", ".join(matched_groups)
    elif required_matched > 0:
        score = score_partial
        summary = (
            "Đạt một phần: có "
            + ", ".join(matched_groups)
            + "; thiếu "
            + ", ".join(missing_required)
        )
    else:
        score = score_none
        summary = "Không phát hiện các yếu tố bắt buộc trong transcript: " + ", ".join(
            g.get("name", "?") for g in required_groups
        )

    evidence = summary
    if evidence_snippets:
        evidence += "\nTrích đoạn: " + " | ".join(evidence_snippets[:3])

    return score, evidence


def auto_score_criterion(criterion, transcript_text: str) -> tuple[float | None, str | None]:
    if criterion.check_type != "keyword" or not criterion.check_config:
        return None, None
    score, evidence = evaluate_keyword_criterion(transcript_text, criterion.check_config)
    return score, evidence


def compute_total(criteria: list, final_scores: dict[str, float]) -> tuple[float | None, list[str]]:
    """final_scores keyed by criterion_id. Returns (weighted_total, list of criterion ids missing a score)."""
    total = 0.0
    weight_sum = 0.0
    missing: list[str] = []
    for c in criteria:
        if not c.include_in_total or not c.weight:
            continue
        score = final_scores.get(c.id)
        if score is None:
            missing.append(c.id)
            continue
        total += score * c.weight
        weight_sum += c.weight
    if weight_sum == 0:
        return None, missing
    return round(total, 2), missing


def classify(total_score: float | None, thresholds: list[dict[str, Any]]) -> str | None:
    if total_score is None or not thresholds:
        return None
    ordered = sorted(thresholds, key=lambda t: t["min"], reverse=True)
    for t in ordered:
        if total_score >= t["min"]:
            return t["label"]
    return ordered[-1]["label"] if ordered else None
