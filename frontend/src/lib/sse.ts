const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8014";

export function createAssistantStream(query: string, sessionId: string, reviewPolicy: string) {
  // SSE 这里走 GET + querystring，前端接起来最省事，也方便直接在浏览器里排查。
  const params = new URLSearchParams({
    question: query,
    session_id: sessionId,
    review_policy: reviewPolicy
  });

  return new EventSource(`${API_BASE_URL}/v1/assistant/run/stream?${params.toString()}`);
}

export function closeAssistantStream(stream: EventSource | null) {
  // 会话切换、重新提问、组件卸载时都要记得收掉旧连接，不然前端会串流。
  if (stream) {
    stream.close();
  }
}
