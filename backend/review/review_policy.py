import re
from dataclasses import dataclass
from typing import Dict, List

from config import (
    REVIEW_MAX_SOURCE_COUNT,
    REVIEW_MIN_DOMINANT_SOURCE_RATIO,
    REVIEW_MIN_EVIDENCE_COUNT,
    REVIEW_MIN_TOP_SCORE,
)
ENTITY_PATTERNS = [
    re.compile(r"患者姓名为([\u4e00-\u9fff]{2,4})"),
    re.compile(r"([\u4e00-\u9fff]{2,4})最近一次体检"),
    re.compile(r"根据([\u4e00-\u9fff]{2,4})的"),
    re.compile(r"([\u4e00-\u9fff]{2,4})的医疗历史"),
]


@dataclass
class ReviewAssessment:
    requires_human_review: bool
    reasons: List[str]
    metrics: Dict[str, float]
    detected_entities: List[str]


def assess_review_need(question: str, evidence: List, metrics: Dict[str, float]) -> ReviewAssessment:
    reasons: List[str] = []
    entities = sorted(extract_entities(evidence))
    evidence_count = int(metrics.get("top_evidence_count", 0))
    max_score = float(metrics.get("max_rerank_score", 0.0))
    source_count = int(metrics.get("source_count", 0))
    dominant_ratio = float(metrics.get("dominant_source_ratio", 0.0))

    if evidence_count < REVIEW_MIN_EVIDENCE_COUNT:
        reasons.append(
            f"Top evidence count is {evidence_count}, below the threshold {REVIEW_MIN_EVIDENCE_COUNT}."
        )
    if max_score < REVIEW_MIN_TOP_SCORE:
        reasons.append(
            f"Highest rerank score is {max_score:.4f}, below the threshold {REVIEW_MIN_TOP_SCORE:.2f}."
        )
    if source_count > REVIEW_MAX_SOURCE_COUNT:
        reasons.append(
            f"Evidence comes from {source_count} distinct sources, above the allowed {REVIEW_MAX_SOURCE_COUNT}."
        )
    if source_count > 1 and dominant_ratio < REVIEW_MIN_DOMINANT_SOURCE_RATIO:
        reasons.append(
            f"Dominant source ratio is {dominant_ratio:.2f}, below the threshold {REVIEW_MIN_DOMINANT_SOURCE_RATIO:.2f}."
        )
    if len(entities) > 1:
        reasons.append(f"Evidence mentions multiple entities: {', '.join(entities)}.")
    if is_high_risk_query(question) and evidence_count == 0:
        reasons.append("High-risk question detected without supporting evidence.")

    return ReviewAssessment(
        requires_human_review=bool(reasons),
        reasons=reasons,
        metrics=metrics,
        detected_entities=entities,
    )


def summarize_assessment(assessment: ReviewAssessment) -> str:
    if not assessment.reasons:
        return "Rule checks passed."
    return " ".join(assessment.reasons)


def extract_entities(evidence: List) -> set[str]:
    entities: set[str] = set()
    for item in evidence[:5]:
        text = item.text if hasattr(item, "text") else str(item.get("text", ""))
        for pattern in ENTITY_PATTERNS:
            for match in pattern.findall(text):
                if match:
                    entities.add(match)
    return entities


def is_high_risk_query(question: str) -> bool:
    normalized = question.lower()
    markers = [
        "健康",
        "risk",
        "治疗",
        "diagnosis",
        "legal",
        "financial",
        "药",
        "建议",
    ]
    return any(marker in normalized for marker in markers)
