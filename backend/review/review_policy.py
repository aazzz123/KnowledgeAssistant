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
    re.compile(r"对象名称为([\u4e00-\u9fffA-Za-z0-9_-]{2,30})"),
    re.compile(r"([\u4e00-\u9fffA-Za-z0-9_-]{2,30})最近一次记录"),
    re.compile(r"根据([\u4e00-\u9fffA-Za-z0-9_-]{2,30})的"),
    re.compile(r"([\u4e00-\u9fffA-Za-z0-9_-]{2,30})的历史记录"),
]


@dataclass
class ReviewAssessment:
    requires_human_review: bool
    reasons: List[str]
    metrics: Dict[str, float]
    detected_entities: List[str]


def assess_review_need(question: str, evidence: List, metrics: Dict[str, float]) -> ReviewAssessment:
    """根据证据情况做规则级审核判断。"""
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

    # 这里只做保守判断：宁可多进一次人工审核，也不让证据不足的问题直接放行。
    return ReviewAssessment(
        requires_human_review=bool(reasons),
        reasons=reasons,
        metrics=metrics,
        detected_entities=entities,
    )


def summarize_assessment(assessment: ReviewAssessment) -> str:
    """把规则判断压成一段简短说明，方便继续传给模型。"""
    if not assessment.reasons:
        return "Rule checks passed."
    return " ".join(assessment.reasons)


def extract_entities(evidence: List) -> set[str]:
    """从证据文本里粗略抓取对象名，用来兜底多对象混淆场景。"""
    entities: set[str] = set()
    for item in evidence[:5]:
        text = item.text if hasattr(item, "text") else str(item.get("text", ""))
        for pattern in ENTITY_PATTERNS:
            for match in pattern.findall(text):
                if match:
                    entities.add(match)
    return entities


def is_high_risk_query(question: str) -> bool:
    """先用轻量关键词做一层高风险识别，避免每次都走模型判断。"""
    normalized = question.lower()
    markers = [
        "risk",
        "legal",
        "financial",
        "compliance",
        "contract",
        "approval",
        "合规",
        "财务",
        "合同",
        "审批",
        "风险",
        "建议",
    ]
    return any(marker in normalized for marker in markers)
