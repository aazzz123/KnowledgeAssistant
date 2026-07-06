import type {
  ExportPdfResponse,
  FeedbackResponse,
  SessionMemoryResponse,
  StructuredAnswerPayload,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8014";

export async function runAssistant(payload: {
  question: string;
  session_id?: string;
  review_policy?: "auto" | "always" | "never";
}) {
  const response = await fetch(`${API_BASE_URL}/v1/assistant/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`runAssistant failed: ${response.status}`);
  }

  return response.json();
}

export async function submitFeedback(payload: {
  task_id: string;
  approved: boolean;
  feedback: string;
}): Promise<FeedbackResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/assistant/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`submitFeedback failed: ${response.status}`);
  }

  return response.json();
}

export async function getSessionMemory(sessionId: string): Promise<SessionMemoryResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/memory/sessions/${sessionId}`);
  if (!response.ok) {
    throw new Error(`getSessionMemory failed: ${response.status}`);
  }
  return response.json();
}

export async function exportConversationPdf(payload: {
  session_id: string;
  question: string;
  title?: string;
  answer_payload?: StructuredAnswerPayload | null;
  answer_text?: string;
}): Promise<ExportPdfResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/assistant/export-pdf`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`exportConversationPdf failed: ${response.status}`);
  }
  return response.json();
}
