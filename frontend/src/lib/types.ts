export type ReviewPolicy = "auto" | "always" | "never";

export type StructuredAnswerPayload = {
  conclusion: string;
  basis: string[];
  citations: string[];
  evidence_gaps: string[];
  review_note: string;
};

export type EvidenceMetadata = {
  paper_id: string;
  title: string;
  year: string;
  section: string;
  page: string;
  paragraph_range: string;
  source: string;
  chunk_index: number;
};

export type EvidenceItem = {
  evidence_id: string;
  text: string;
  metadata: EvidenceMetadata;
  dense_score: number;
  bm25_score: number;
  hybrid_score: number;
  rerank_score: number;
};

export type AssistantRunResponse = {
  task_id: string;
  session_id: string;
  status: string;
  question: string;
  retrieved_context: string;
  retrieved_evidence: EvidenceItem[];
  review_metrics: Record<string, number | string>;
  draft: string;
  draft_payload?: StructuredAnswerPayload | null;
  answer_payload?: StructuredAnswerPayload | null;
  review_decision: string;
  review_reason: string;
};

export type FeedbackResponse = {
  task_id: string;
  session_id: string;
  status: string;
  answer: string;
  answer_payload?: StructuredAnswerPayload | null;
  report_path?: string | null;
};

export type ExportPdfResponse = {
  title: string;
  report_path: string;
};

export type SessionMemoryResponse = {
  session_id: string;
  current_topic: string;
  recent_questions: string[];
  confirmed_answers: string[];
  summary_context: string;
  short_term: Array<Record<string, unknown>>;
  long_term: Array<Record<string, unknown>>;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  question?: string;
  conclusion?: string;
  basisPreview?: string[];
  answerPayload?: StructuredAnswerPayload | null;
  retrievedEvidence?: EvidenceItem[];
  reviewMetrics?: Record<string, number | string>;
  reviewReason?: string;
  status?: "streaming" | "waiting_feedback" | "completed" | "error";
  draft?: string;
  taskId?: string;
  exportPath?: string;
};

export type SessionEntry = {
  id: string;
  title: string;
  createdAt: number;
};
