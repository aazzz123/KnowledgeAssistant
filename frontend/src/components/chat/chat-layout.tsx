"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  exportConversationPdf,
  getSessionMemory,
  submitFeedback,
} from "@/lib/api";
import { closeAssistantStream, createAssistantStream } from "@/lib/sse";
import type {
  AssistantRunResponse,
  ChatMessage,
  FeedbackResponse,
  SessionEntry,
  SessionMemoryResponse,
} from "@/lib/types";
import { AnswerCard } from "@/components/chat/answer-card";
import { MessageList } from "@/components/chat/message-list";
import { QuestionInput } from "@/components/chat/question-input";
import { SessionsPanel } from "@/components/chat/sessions-panel";
import { EvidenceDrawer } from "@/components/evidence/evidence-drawer";
import { MemoryDrawer } from "@/components/memory/memory-drawer";
import { ReviewPanel } from "@/components/review/review-panel";

const STORAGE_KEY = "knowledge-assistant-sessions";

type SessionState = {
  entry: SessionEntry;
  messages: ChatMessage[];
};

function createSession(title = "New Session"): SessionState {
  // 会话 id 只在前端本地用，够唯一就行，不额外引入 uuid 依赖了。
  const id = `session-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  return {
    entry: {
      id,
      title,
      createdAt: Date.now(),
    },
    messages: [],
  };
}

export function ChatLayout() {
  const initialSession = useMemo(() => createSession(), []);
  const [sessions, setSessions] = useState<SessionState[]>([initialSession]);
  const [activeSessionId, setActiveSessionId] = useState<string>(initialSession.entry.id);
  const [reviewPolicy, setReviewPolicy] = useState<"auto" | "always" | "never">("auto");
  const [activeReviewMessageId, setActiveReviewMessageId] = useState<string | null>(null);
  const [sessionMemory, setSessionMemory] = useState<SessionMemoryResponse | null>(null);
  const [streamStatus, setStreamStatus] = useState<string>("");
  const streamRef = useRef<EventSource | null>(null);

  const activeSession =
    sessions.find((session) => session.entry.id === activeSessionId) ?? sessions[0];
  const messages = activeSession?.messages ?? [];
  const latestAssistantMessage =
    [...messages].reverse().find((message) => message.role === "assistant") ?? null;
  const reviewMessage =
    messages.find((message) => message.id === activeReviewMessageId) ?? null;

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return;
    }
    try {
      const parsed = JSON.parse(stored) as SessionState[];
      if (Array.isArray(parsed) && parsed.length > 0) {
        setSessions(parsed);
        setActiveSessionId(parsed[0].entry.id);
      }
    } catch {
      // 本地缓存如果结构坏了，直接丢掉比继续带着脏数据跑更省事。
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    let mounted = true;
    // 会话切换后顺手把记忆面板刷新掉，右侧信息就能跟当前聊天保持一致。
    getSessionMemory(activeSessionId)
      .then((payload) => {
        if (mounted) {
          setSessionMemory(payload);
        }
      })
      .catch(() => {
        if (mounted) {
          setSessionMemory(null);
        }
      });
    return () => {
      mounted = false;
    };
  }, [activeSessionId, messages.length]);

  useEffect(() => {
    return () => {
      closeAssistantStream(streamRef.current);
    };
  }, []);

  function updateSessionById(
    sessionId: string,
    updater: (session: SessionState) => SessionState,
  ) {
    setSessions((current) =>
      current.map((session) => (session.entry.id === sessionId ? updater(session) : session)),
    );
  }

  function handleCreateSession() {
    const session = createSession(`Session ${sessions.length + 1}`);
    setSessions((current) => [session, ...current]);
    setActiveSessionId(session.entry.id);
    setActiveReviewMessageId(null);
    setSessionMemory(null);
    setStreamStatus("");
  }

  function handleSelectSession(sessionId: string) {
    closeAssistantStream(streamRef.current);
    streamRef.current = null;
    setActiveSessionId(sessionId);
    setActiveReviewMessageId(null);
    setStreamStatus("");
  }

  function handleDeleteSession(sessionId: string) {
    closeAssistantStream(streamRef.current);
    streamRef.current = null;

    setSessions((current) => {
      const remaining = current.filter((session) => session.entry.id !== sessionId);
      if (remaining.length > 0) {
        if (sessionId === activeSessionId) {
          // 删掉当前会话时，顺手把右侧审核态和记忆态也一起切干净。
          setActiveSessionId(remaining[0].entry.id);
          setActiveReviewMessageId(null);
          setSessionMemory(null);
          setStreamStatus("");
        }
        return remaining;
      }

      const fallback = createSession();
      setActiveSessionId(fallback.entry.id);
      setActiveReviewMessageId(null);
      setSessionMemory(null);
      setStreamStatus("");
      return [fallback];
    });
  }

  async function handleQuestionSubmit(question: string) {
    if (isExportIntent(question)) {
      await handleExportForSession(activeSessionId, question);
      return;
    }

    closeAssistantStream(streamRef.current);
    const targetSessionId = activeSessionId;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      question,
    };
    const assistantMessageId = `assistant-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    const placeholderAssistant: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      conclusion: "",
      status: "streaming",
    };

    updateSessionById(targetSessionId, (session) => {
      const nextTitle =
        session.messages.length === 0
          ? question.slice(0, 18) || session.entry.title
          : session.entry.title;
      return {
        entry: { ...session.entry, title: nextTitle },
        messages: [...session.messages, userMessage, placeholderAssistant],
      };
    });

    setStreamStatus("Connecting...");
    const stream = createAssistantStream(question, targetSessionId, reviewPolicy);
    streamRef.current = stream;

    // 这里把“阶段事件”和“答案增量事件”拆开处理，前端体验会比最后一次性出结果自然很多。
    stream.addEventListener("task_started", () => setStreamStatus("Task started"));
    stream.addEventListener("retrieval_completed", () => setStreamStatus("Evidence retrieved"));
    stream.addEventListener("draft_completed", () => setStreamStatus("Draft completed"));
    stream.addEventListener("review_decided", () => setStreamStatus("Review decided"));
    stream.addEventListener("draft_delta", (event) => {
      const payload = safeParseMessageEvent(event);
      updateMessage(targetSessionId, assistantMessageId, {
        conclusion: payload?.text || "",
        status: "streaming",
      });
      setStreamStatus("Drafting answer...");
    });
    stream.addEventListener("answer_delta", (event) => {
      const payload = safeParseMessageEvent(event);
      updateMessage(targetSessionId, assistantMessageId, {
        conclusion: payload?.text || "",
        status: "streaming",
      });
      setStreamStatus("Writing final answer...");
    });

    stream.addEventListener("review_required", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as AssistantRunResponse;
      applyRunResponseToMessage(targetSessionId, assistantMessageId, payload, "waiting_feedback");
      setActiveReviewMessageId(assistantMessageId);
      setStreamStatus("Manual review required");
    });

    stream.addEventListener("final_completed", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as AssistantRunResponse;
      applyRunResponseToMessage(targetSessionId, assistantMessageId, payload, "completed");
      setStreamStatus("Answer completed");
    });

    stream.addEventListener("error", (event) => {
      const detail = safeParseEventData(event);
      updateMessage(targetSessionId, assistantMessageId, {
        conclusion: detail?.detail || "Request failed. Please inspect backend logs.",
        status: "error",
      });
      setStreamStatus("Request failed");
    });

    stream.addEventListener("stream_end", () => {
      closeAssistantStream(streamRef.current);
      streamRef.current = null;
    });
  }

  function applyRunResponseToMessage(
    sessionId: string,
    messageId: string,
    payload: AssistantRunResponse,
    status: "waiting_feedback" | "completed",
  ) {
    // 最终落库和展示仍然以结构化结果为准，流式 conclusion 只是中间态。
    updateMessage(sessionId, messageId, {
      taskId: payload.task_id,
      conclusion:
        payload.answer_payload?.conclusion ||
        payload.draft_payload?.conclusion ||
        payload.draft ||
        "No conclusion available.",
      basisPreview: (
        payload.answer_payload?.basis ??
        payload.draft_payload?.basis ??
        []
      ).slice(0, 3),
      answerPayload: payload.answer_payload ?? payload.draft_payload,
      retrievedEvidence: payload.retrieved_evidence,
      reviewMetrics: payload.review_metrics,
      reviewReason: payload.review_reason,
      draft: payload.draft,
      status,
    });
  }

  function updateMessage(
    sessionId: string,
    messageId: string,
    partial: Partial<ChatMessage>,
  ) {
    updateSessionById(sessionId, (session) => ({
      ...session,
      messages: session.messages.map((message) =>
        message.id === messageId ? { ...message, ...partial } : message,
      ),
    }));
  }

  async function handleReviewSubmit(approved: boolean, feedback: string) {
    if (!reviewMessage?.taskId) {
      return;
    }
    setStreamStatus("Submitting review...");
    const payload: FeedbackResponse = await submitFeedback({
      task_id: reviewMessage.taskId,
      approved,
      feedback,
    });
    updateMessage(activeSessionId, reviewMessage.id, {
      conclusion: payload.answer_payload?.conclusion || payload.answer,
      basisPreview: (payload.answer_payload?.basis ?? []).slice(0, 3),
      answerPayload: payload.answer_payload,
      status: "completed",
    });
    setActiveReviewMessageId(null);
    setStreamStatus("Review completed");
  }

  async function handleExportForSession(sessionId: string, exportQuestion?: string) {
    const session = sessions.find((item) => item.entry.id === sessionId);
    const latestAssistant =
      [...(session?.messages ?? [])].reverse().find((message) => message.role === "assistant") ?? null;
    const latestUser =
      [...(session?.messages ?? [])].reverse().find((message) => message.role === "user") ?? null;

    if (!latestAssistant) {
      setStreamStatus("No answer is available to export in this session");
      return;
    }

    // 导出默认取这个会话里最近一条 assistant 回复，省得用户再手动选一次。
    setStreamStatus("Exporting PDF...");
    const result = await exportConversationPdf({
      session_id: sessionId,
      question: exportQuestion || latestUser?.question || session?.entry.title || "Knowledge export",
      answer_payload: latestAssistant.answerPayload ?? null,
      answer_text: latestAssistant.conclusion || latestAssistant.draft || "",
    });

    updateMessage(sessionId, latestAssistant.id, {
      exportPath: result.report_path,
    });
    setStreamStatus(`PDF exported: ${result.title}`);
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto grid min-h-screen max-w-[1600px] grid-cols-12 gap-4 p-4">
        <aside className="col-span-3 space-y-4">
          <SessionsPanel
            sessions={sessions.map((item) => item.entry)}
            activeSessionId={activeSessionId}
            onCreateSession={handleCreateSession}
            onSelectSession={handleSelectSession}
            onExportSession={handleExportForSession}
            onDeleteSession={handleDeleteSession}
          />
          <MemoryDrawer memory={sessionMemory} />
        </aside>
        <section className="col-span-6 flex min-h-[80vh] flex-col rounded-[32px] bg-white shadow-sm ring-1 ring-black/5">
          <header className="border-b border-black/5 px-6 py-5">
            <h1 className="text-2xl font-semibold tracking-tight">KnowledgeAssistant</h1>
            {streamStatus ? (
              <p className="mt-3 text-xs uppercase tracking-[0.2em] text-clay">{streamStatus}</p>
            ) : null}
          </header>
          <div className="flex-1 overflow-y-scroll px-6 py-5 [scrollbar-gutter:stable]">
            <div className="space-y-4 pr-1">
              <MessageList messages={messages} />
              {latestAssistantMessage?.role === "assistant" ? (
                <AnswerCard message={latestAssistantMessage} />
              ) : null}
            </div>
          </div>
          <div className="border-t border-black/5 px-6 py-5">
            <QuestionInput
              reviewPolicy={reviewPolicy}
              onReviewPolicyChange={setReviewPolicy}
              onSubmit={handleQuestionSubmit}
            />
          </div>
        </section>
        <aside className="col-span-3 space-y-4">
          <EvidenceDrawer evidence={latestAssistantMessage?.retrievedEvidence ?? []} />
          <ReviewPanel message={reviewMessage} onSubmit={handleReviewSubmit} />
        </aside>
      </div>
    </main>
  );
}

function safeParseEventData(event: Event) {
  try {
    return JSON.parse((event as MessageEvent).data) as { detail?: string };
  } catch {
    return null;
  }
}

function safeParseMessageEvent(event: Event) {
  try {
    return JSON.parse((event as MessageEvent).data) as { text?: string };
  } catch {
    return null;
  }
}

function isExportIntent(question: string) {
  return /(save|export|pdf|保存|导出|生成)/i.test(question);
}
