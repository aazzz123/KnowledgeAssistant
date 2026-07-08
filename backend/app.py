
"""FastAPI 服务入口，负责对外暴露问答、流式输出、审核和导出接口。"""

import json
import logging
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from queue import Queue
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import APP_NAME, LLM_TYPE, MEMORY_DIR, PORT
from llm_factory import build_llm
from memory.session_memory import SessionMemoryStore
from models.schemas import (
    AssistantRunRequest,
    AssistantRunResponse,
    ExportPdfRequest,
    ExportPdfResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from observability.metrics import metrics_recorder
from review.review_store import ReviewStore
from tools.save_pdf_tool import save_text_to_pdf
from workflows.assistant_graph import KnowledgeAssistantFlow, finalize_with_feedback


logger = logging.getLogger(__name__)
llm = None
review_store = ReviewStore()
session_memory_store = SessionMemoryStore(MEMORY_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """在服务启动时初始化模型客户端。"""
    del app
    global llm
    llm = build_llm(llm_type=LLM_TYPE)
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """服务健康检查接口。"""
    return {"status": "ok", "app": APP_NAME}


@app.post("/v1/assistant/run", response_model=AssistantRunResponse)
async def run_assistant(request: AssistantRunRequest):
    """同步执行整条问答链路，直接返回最终结果或待审核草稿。"""
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM is not initialized.")

    try:
        task, started_at = execute_assistant_run(
            question=request.question,
            session_id=request.session_id,
            review_policy=request.review_policy,
        )
        return task_to_response(task)
    except Exception as exc:
        logger.exception("Failed to run assistant workflow.")
        metrics_recorder.record(
            "task_error",
            stage="run",
            question=request.question,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/v1/assistant/run/stream")
async def run_assistant_stream(
    question: str = Query(..., min_length=1),
    session_id: str | None = Query(default=None),
    review_policy: str = Query(default="auto"),
):
    """按 SSE 方式推送阶段事件和答案增量。"""
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM is not initialized.")

    # SSE 这一层只负责转发事件，真正的工作还是放到后台线程里跑，避免阻塞主请求线程。
    queue: Queue[tuple[str, dict[str, Any]]] = Queue()

    def on_stage(event_name: str, payload: dict[str, Any]):
        """把流程中间事件丢进队列，交给外层 SSE 持续输出。"""
        queue.put((event_name, payload))

    def worker():
        """后台线程里执行完整流程，并把结果逐步推给前端。"""
        started_at = time.perf_counter()
        try:
            task, _ = execute_assistant_run(
                question=question,
                session_id=session_id,
                review_policy=review_policy,
                on_stage=on_stage,
            )
            final_payload = serialize_task(task)
            final_payload["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
            if task.status == "waiting_feedback":
                queue.put(("review_required", final_payload))
            else:
                queue.put(("final_completed", final_payload))
            queue.put(("stream_end", {"status": task.status, "task_id": task.task_id}))
        except Exception as exc:
            logger.exception("Failed to stream assistant workflow.")
            queue.put(("error", {"detail": str(exc)}))
            queue.put(("stream_end", {"status": "error"}))

    def event_stream():
        """把队列里的事件转成标准 SSE 文本。"""
        stream_thread = threading.Thread(target=worker, daemon=True)
        stream_thread.start()
        while True:
            event_name, payload = queue.get()
            yield sse_message(event_name, payload)
            if event_name == "stream_end":
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/v1/assistant/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """提交人工审核结果，并在需要时重新定稿。"""
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM is not initialized.")

    task = review_store.get(request.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.status == "completed":
        return FeedbackResponse(
            task_id=task.task_id,
            session_id=task.session_id,
            status=task.status,
            answer=task.answer,
            answer_payload=task.answer_payload,
            report_path=task.metadata.get("report_path"),
        )

    try:
        started_at = time.perf_counter()
        task = finalize_with_feedback(
            llm=llm,
            memory=session_memory_store,
            task=task,
            feedback=request.feedback,
            approved=request.approved,
        )
        review_store.update(task)
        metrics_recorder.record(
            "task_completed",
            task_id=task.task_id,
            session_id=task.session_id,
            approved=request.approved,
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            answer_chars=len(task.answer),
            review_metrics=task.review_metrics,
        )
        return FeedbackResponse(
            task_id=task.task_id,
            session_id=task.session_id,
            status=task.status,
            answer=task.answer,
            answer_payload=task.answer_payload,
            report_path=task.metadata.get("report_path"),
        )
    except Exception as exc:
        logger.exception("Failed to finalize assistant workflow.")
        metrics_recorder.record(
            "task_error",
            stage="feedback",
            task_id=request.task_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/assistant/export-pdf", response_model=ExportPdfResponse)
async def export_pdf(request: ExportPdfRequest):
    """把当前回答导出成 PDF。"""
    title = derive_export_title(request.title or request.question or "知识问答记录")
    content = build_export_content(
        title=title,
        answer_payload=request.answer_payload,
        answer_text=request.answer_text,
    )
    report_path = save_text_to_pdf(content, filename=f"{title}.pdf")
    return ExportPdfResponse(title=title, report_path=report_path)


@app.get("/v1/assistant/tasks/{task_id}")
async def get_task(task_id: str):
    """查询审核任务详情。"""
    task = review_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@app.get("/v1/memory/sessions/{session_id}")
async def get_session_memory(session_id: str):
    """获取指定会话的记忆快照。"""
    return {"session_id": session_id, **session_memory_store.load(session_id)}


@app.get("/v1/observability/events")
async def get_observability_events(limit: int = Query(default=100, ge=1, le=1000)):
    """获取最近的运行事件列表。"""
    return {"events": metrics_recorder.load_events(limit=limit)}


@app.get("/v1/observability/summary")
async def get_observability_summary():
    """获取聚合后的运行概览。"""
    return metrics_recorder.summary()


def execute_assistant_run(
    question: str,
    session_id: str | None,
    review_policy: str,
    on_stage=None,
):
    """执行问答流程，并根据审核决策决定是否直接定稿。"""
    started_at = time.perf_counter()
    normalized_session_id = session_id or str(uuid.uuid4())
    normalized_review_policy = review_policy.lower()
    if normalized_review_policy not in {"auto", "always", "never"}:
        raise ValueError("review_policy must be one of: auto, always, never.")

    metrics_recorder.record(
        "task_started",
        session_id=normalized_session_id,
        question=question,
        review_policy=normalized_review_policy,
    )
    flow = KnowledgeAssistantFlow(
        llm=llm,
        memory=session_memory_store,
        question=question,
        session_id=normalized_session_id,
    )

    # 同一个流程既支持同步执行，也支持按阶段推送事件，前端流式模式走的是 stepwise 这条路。
    if on_stage:
        flow.kickoff_stepwise(review_policy=normalized_review_policy, on_stage=on_stage)
    else:
        flow.kickoff(review_policy=normalized_review_policy)

    task = flow.build_review_task()

    # 这里只先产出待审核任务，是否直接定稿由后面的审核策略决定。
    if task.review_decision == "REVIEW_REQUIRED":
        review_store.create(task)
        metrics_recorder.record(
            "task_waiting_feedback",
            task_id=task.task_id,
            session_id=task.session_id,
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            draft_chars=len(task.draft),
            review_decision=task.review_decision,
            review_reason=task.review_reason,
            review_metrics=task.review_metrics,
        )
        return task, started_at

    task = finalize_with_feedback(
        llm=llm,
        memory=session_memory_store,
        task=task,
        feedback="Auto-approved by review policy or review decision agent.",
        approved=True,
        on_conclusion_delta=(
            lambda text: on_stage("answer_delta", {"text": text}) if on_stage else None
        ),
    )
    review_store.create(task)
    metrics_recorder.record(
        "task_completed",
        task_id=task.task_id,
        session_id=task.session_id,
        latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        answer_chars=len(task.answer),
        review_decision=task.review_decision,
        review_reason=task.review_reason,
        review_metrics=task.review_metrics,
    )
    return task, started_at


def task_to_response(task):
    """把内部任务对象转换成接口响应结构。"""
    if task.status == "waiting_feedback":
        return AssistantRunResponse(
            task_id=task.task_id,
            session_id=task.session_id,
            status=task.status,
            question=task.question,
            retrieved_context=task.retrieved_context,
            retrieved_evidence=task.retrieved_evidence,
            review_metrics=task.review_metrics,
            draft=task.draft,
            draft_payload=task.draft_payload,
            review_decision=task.review_decision,
            review_reason=task.review_reason,
        )

    return AssistantRunResponse(
        task_id=task.task_id,
        session_id=task.session_id,
        status=task.status,
        question=task.question,
        retrieved_context=task.retrieved_context,
        retrieved_evidence=task.retrieved_evidence,
        review_metrics=task.review_metrics,
        draft=task.answer,
        draft_payload=task.draft_payload,
        answer_payload=task.answer_payload,
        review_decision=task.review_decision,
        review_reason=task.review_reason,
    )


def serialize_task(task):
    """把内部任务拍平成前端可直接消费的字典。"""
    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "status": task.status,
        "question": task.question,
        "retrieved_context": task.retrieved_context,
        "retrieved_evidence": [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in task.retrieved_evidence
        ],
        "review_metrics": task.review_metrics,
        "draft": task.draft,
        "draft_payload": (
            task.draft_payload.model_dump()
            if hasattr(task.draft_payload, "model_dump")
            else task.draft_payload
        ),
        "answer": task.answer,
        "answer_payload": (
            task.answer_payload.model_dump()
            if hasattr(task.answer_payload, "model_dump")
            else task.answer_payload
        ),
        "review_decision": task.review_decision,
        "review_reason": task.review_reason,
        "report_path": task.metadata.get("report_path"),
    }


def sse_message(event_name: str, payload: dict[str, Any]) -> str:
    """把事件名和载荷编码成标准 SSE 文本。"""
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def derive_export_title(raw: str) -> str:
    """从用户问题里提炼一个适合当 PDF 文件名的标题。"""
    text = (raw or "").strip()
    text = re.sub(r"(?i)\bpdf\b", "", text)
    text = re.sub(r"(请帮我|帮我|把内容|回答|结果|最近一次对话|最近的对话)", "", text)
    text = re.sub(r"(保存为?|导出为?|生成|输出|打印)", "", text)
    text = re.sub(r"(总结|概括|整理)", "", text)
    text = re.sub(r"[，。？！；:：]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_")
    return text[:40] or "知识问答记录"


def build_export_content(title: str, answer_payload, answer_text: str) -> str:
    """把回答整理成适合导出的正文格式。"""
    if answer_payload:
        basis = answer_payload.basis or []
        conclusion = answer_payload.conclusion or ""
        lines = [title, "", "依据:"]
        lines.extend(f"- {item}" for item in basis)
        lines.extend(["", "结论:", conclusion])
        return "\n".join(lines).strip()
    return "\n".join([title, "", answer_text.strip()]).strip()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
