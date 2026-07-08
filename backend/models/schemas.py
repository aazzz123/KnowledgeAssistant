from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvidenceMetadata(BaseModel):
    document_id: str = Field(default="")
    title: str = ""
    year: str = ""
    section: str = ""
    page: str = ""
    paragraph_range: str = ""
    source: str = ""
    chunk_index: int = 0


class EvidenceItem(BaseModel):
    evidence_id: str
    text: str
    metadata: EvidenceMetadata
    dense_score: float = 0.0
    bm25_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float = 0.0


class StructuredAnswerPayload(BaseModel):
    conclusion: str = ""
    basis: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    review_note: str = ""


class AssistantRunRequest(BaseModel):
    question: str = Field(..., description="User question for the knowledge assistant.")
    session_id: Optional[str] = Field(default=None, description="Conversation/session id.")
    review_policy: str = Field(
        default="auto",
        description="Human review policy: auto, always, or never.",
    )


class AssistantRunResponse(BaseModel):
    task_id: str
    session_id: str
    status: str
    question: str
    retrieved_context: str
    retrieved_evidence: List[EvidenceItem] = Field(default_factory=list)
    review_metrics: Dict[str, Any] = Field(default_factory=dict)
    draft: str
    draft_payload: Optional[StructuredAnswerPayload] = None
    answer_payload: Optional[StructuredAnswerPayload] = None
    review_decision: str = "unknown"
    review_reason: str = ""


class FeedbackRequest(BaseModel):
    task_id: str
    approved: bool = False
    feedback: str = ""


class FeedbackResponse(BaseModel):
    task_id: str
    session_id: str
    status: str
    answer: str
    answer_payload: Optional[StructuredAnswerPayload] = None
    report_path: Optional[str] = None


class ExportPdfRequest(BaseModel):
    session_id: str
    question: str = ""
    title: str = ""
    answer_payload: Optional[StructuredAnswerPayload] = None
    answer_text: str = ""


class ExportPdfResponse(BaseModel):
    title: str
    report_path: str


class TaskState(BaseModel):
    task_id: str
    session_id: str
    status: str
    question: str
    retrieved_context: str = ""
    retrieved_evidence: List[EvidenceItem] = Field(default_factory=list)
    review_metrics: Dict[str, Any] = Field(default_factory=dict)
    draft: str = ""
    draft_payload: Optional[StructuredAnswerPayload] = None
    feedback: str = ""
    approved: bool = False
    answer: str = ""
    answer_payload: Optional[StructuredAnswerPayload] = None
    review_decision: str = "unknown"
    review_reason: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    task_id: str
    question: str
    retrieved_context: str
    draft: str
    draft_payload: Optional[StructuredAnswerPayload] = None
    feedback: str = ""
    answer: str = ""
    answer_payload: Optional[StructuredAnswerPayload] = None
    confirmed: bool = False


class SessionMemory(BaseModel):
    session_id: str
    current_topic: str = ""
    recent_questions: List[str] = Field(default_factory=list)
    confirmed_answers: List[str] = Field(default_factory=list)
    summary_context: str = ""
    short_term: List[MemoryRecord] = Field(default_factory=list)
    long_term: List[Dict[str, Any]] = Field(default_factory=list)
