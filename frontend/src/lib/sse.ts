const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8014";

export function createAssistantStream(query: string, sessionId: string, reviewPolicy: string) {
  const params = new URLSearchParams({
    question: query,
    session_id: sessionId,
    review_policy: reviewPolicy
  });

  return new EventSource(`${API_BASE_URL}/v1/assistant/run/stream?${params.toString()}`);
}

export function closeAssistantStream(stream: EventSource | null) {
  if (stream) {
    stream.close();
  }
}
