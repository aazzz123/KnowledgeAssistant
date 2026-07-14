"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AnswerCard } from "@/components/chat/answer-card";
import { MessageList } from "@/components/chat/message-list";
import { QuestionInput } from "@/components/chat/question-input";
import { SessionsPanel } from "@/components/chat/sessions-panel";
import { EvidenceDrawer } from "@/components/evidence/evidence-drawer";
import { MemoryDrawer } from "@/components/memory/memory-drawer";
import { ReviewPanel } from "@/components/review/review-panel";
import { exportConversationPdf, getSessionMemory, submitFeedback } from "@/lib/api";
import { closeAssistantStream, createAssistantStream } from "@/lib/sse";
import type {
  AssistantRunResponse,
  ChatMessage,
  FeedbackResponse,
  SessionEntry,
  SessionMemoryResponse,
} from "@/lib/types";

const STORAGE_KEY = "knowledge-assistant-sessions";

type SessionState = {
  entry: SessionEntry;
  messages: ChatMessage[];
};

function createSession(title = "新会话"): SessionState {
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

const STATUS_COPY: Record<string, string> = {
  "": "就绪",
  "Connecting...": "连接中",
  "Task started": "任务已开始",
  "Evidence retrieved": "证据已检索",
  "Draft completed": "草稿已完成",
  "Review decided": "审核策略已判定",
  "Drafting answer...": "正在生成草稿",
  "Writing final answer...": "正在生成最终答案",
  "Manual review required": "需要人工审核",
  "Answer completed": "回答已完成",
  "Submitting review...": "正在提交审核",
  "Review completed": "审核已完成",
  "Exporting PDF...": "正在导出 PDF",
  "Request failed": "请求失败",
};

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
  const latestUserMessage =
    [...messages].reverse().find((message) => message.role === "user") ?? null;
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
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    let mounted = true;
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
    const session = createSession(`会话 ${sessions.length + 1}`);
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
        conclusion: detail?.detail || "请求失败，请检查后端日志。",
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
    updateMessage(sessionId, messageId, {
      taskId: payload.task_id,
      conclusion:
        payload.answer_payload?.conclusion ||
        payload.draft_payload?.conclusion ||
        payload.draft ||
        "暂无结论。",
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
      [...(session?.messages ?? [])]
        .reverse()
        .find((message) => message.role === "assistant") ?? null;
    const latestUser =
      [...(session?.messages ?? [])].reverse().find((message) => message.role === "user") ?? null;

    if (!latestAssistant) {
      setStreamStatus("当前会话暂无可导出的答案");
      return;
    }

    setStreamStatus("Exporting PDF...");
    const result = await exportConversationPdf({
      session_id: sessionId,
      question: exportQuestion || latestUser?.question || session?.entry.title || "知识库导出",
      answer_payload: latestAssistant.answerPayload ?? null,
      answer_text: latestAssistant.conclusion || latestAssistant.draft || "",
    });

    updateMessage(sessionId, latestAssistant.id, {
      exportPath: result.report_path,
    });
    setStreamStatus(`PDF exported: ${result.title}`);
  }

  const statusLabel = STATUS_COPY[streamStatus] ?? streamStatus;
  const sessionCount = sessions.length;
  const evidenceCount = latestAssistantMessage?.retrievedEvidence?.length ?? 0;
  const reviewPending = Boolean(reviewMessage);

  return (
    <main className="min-h-[100dvh] px-4 py-4 text-ink sm:px-5 lg:px-6">
      <div className="mx-auto grid max-w-[1680px] gap-4 xl:grid-cols-[300px_minmax(0,1fr)_320px]">
        <aside className="space-y-4 xl:sticky xl:top-4 xl:h-[calc(100dvh-2rem)] xl:overflow-hidden">
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

        <section className="shell-panel flex flex-col overflow-hidden xl:h-[calc(100dvh-2rem)]">
          <div className="shrink-0 border-b border-black/5 px-5 py-4 sm:px-6">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <p className="section-label">知识工作台</p>
                <h1 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-ink sm:text-[2rem]">
                  用更清晰、更从容的方式检索、审核并导出私有知识。
                </h1>
              </div>

              <div className="grid gap-2 sm:grid-cols-3 lg:min-w-[390px]">
                <div className="surface-panel px-4 py-3">
                  <p className="section-label">会话</p>
                  <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{sessionCount}</p>
                  <p className="mt-1 text-sm text-black/55">当前可用的对话线程</p>
                </div>
                <div className="surface-panel px-4 py-3">
                  <p className="section-label">证据</p>
                  <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{evidenceCount}</p>
                  <p className="mt-1 text-sm text-black/55">最近答案关联的证据条目</p>
                </div>
                <div className="surface-panel px-4 py-3">
                  <p className="section-label">审核</p>
                  <p className="mt-2 text-sm font-semibold tracking-[0.02em] text-clay">
                    {reviewPending ? "待处理" : "状态正常"}
                  </p>
                  <p className="mt-2 text-sm text-black/55">
                    {reviewPending
                      ? "右侧面板中有待人工审核的内容。"
                      : "当前会话没有待审批的阻塞任务。"}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="status-pill bg-clay/10 text-clay">{statusLabel}</span>
              <span className="rounded-full border border-black/[0.08] px-3 py-1 text-sm text-black/58">
                审核模式：
                {reviewPolicy === "auto"
                  ? "自动"
                  : reviewPolicy === "always"
                    ? "始终审核"
                    : "从不审核"}
              </span>
              <span className="rounded-full border border-black/[0.08] px-3 py-1 text-sm text-black/58">
                当前会话：{activeSession?.entry.title || "未命名会话"}
              </span>
            </div>
          </div>

          <div className="min-h-0 flex-1 grid gap-0 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="min-h-0 border-b border-black/5 lg:border-b-0 lg:border-r">
              <div className="flex min-h-[52dvh] flex-col xl:h-full xl:min-h-0">
                <div className="chat-scrollbar min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7">
                  {messages.length === 0 ? (
                    <EmptyConversationState />
                  ) : (
                    <div className="space-y-5">
                      <MessageList messages={messages} />
                      {latestAssistantMessage?.role === "assistant" ? (
                        <AnswerCard message={latestAssistantMessage} />
                      ) : null}
                    </div>
                  )}
                </div>
                <div className="shrink-0 border-t border-black/5 px-4 py-4 sm:px-6">
                  <QuestionInput
                    reviewPolicy={reviewPolicy}
                    onReviewPolicyChange={setReviewPolicy}
                    onSubmit={handleQuestionSubmit}
                  />
                </div>
              </div>
            </div>

            <div className="min-h-0 bg-white/35 px-5 py-5 sm:px-6 xl:overflow-y-auto">
              <div className="space-y-4">
                <div className="soft-panel p-4">
                  <p className="section-label">当前上下文</p>
                  <p className="mt-2 text-base font-semibold text-ink">
                    {latestUserMessage?.question || activeSession?.entry.title || "新会话"}
                  </p>
                  <p className="mt-2 text-sm leading-7 text-black/58">
                    在查看答案、证据和导出状态时，始终保持最近一次用户意图清晰可见。
                  </p>
                </div>
                <EvidenceDrawer evidence={latestAssistantMessage?.retrievedEvidence ?? []} />
              </div>
            </div>
          </div>
        </section>

        <aside className="space-y-4 xl:sticky xl:top-4 xl:h-[calc(100dvh-2rem)] xl:overflow-hidden">
          <ReviewPanel message={reviewMessage} onSubmit={handleReviewSubmit} />
        </aside>
      </div>
    </main>
  );
}

function EmptyConversationState() {
  const prompts = [
    "总结最新政策备忘录，并引用最关键的支撑证据。",
    "比较两份内部文档，指出其中的冲突点或证据缺口。",
    "在审核完成后，将当前答案导出为 PDF 报告。",
  ];

  return (
    <div className="flex min-h-[420px] flex-col justify-between rounded-[28px] border border-dashed border-black/10 bg-white/55 p-6 sm:p-8">
      <div>
        <p className="section-label">从这里开始</p>
        <h2 className="mt-3 max-w-xl text-2xl font-semibold tracking-[-0.04em] text-ink sm:text-[2rem]">
          向助手提出一个与文档密切相关的问题，工作区就会围绕它展开。
        </h2>
        <p className="mt-3 max-w-[58ch] text-sm leading-7 text-black/58 sm:text-[15px]">
          左侧会显示会话记忆，右侧显示证据与审核，中间主区域则持续呈现结构化答案。
        </p>
      </div>

      <div className="mt-8 grid gap-3">
        {prompts.map((prompt) => (
          <div className="surface-panel px-4 py-4" key={prompt}>
            <p className="text-sm leading-7 text-black/72">{prompt}</p>
          </div>
        ))}
      </div>
    </div>
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
