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
  // 这个接口是同步版，主要给不需要流式的场景或调试时直接拿完整结果用。
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
  // 审核结果回提后，后端会基于意见重新定稿并回写会话记忆。
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
  // 右侧记忆面板每次切换会话都会来这里拿一个最新快照。
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
  // 导出时优先带结构化答案，后端才能按“依据 + 结论”的固定顺序落 PDF。
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
