import logging
import json
import re
import time
import threading
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
    return {"status": "ok", "app": APP_NAME}


@app.post("/v1/assistant/run", response_model=AssistantRunResponse)
async def run_assistant(request: AssistantRunRequest):
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM is not initialized.")

    try:
        task, started_at = execute_assistant_run(
            question=request.question,
            session_id=request.session_id,
            review_policy=request.review_policy,
        )
        return task_to_response(task, started_at)
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
    if llm is None:
        raise HTTPException(status_code=500, detail="LLM is not initialized.")

    queue: Queue[tuple[str, dict[str, Any]]] = Queue()

    def on_stage(event_name: str, payload: dict[str, Any]):
        queue.put((event_name, payload))

    def worker():
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
    task = review_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@app.get("/v1/memory/sessions/{session_id}")
async def get_session_memory(session_id: str):
    return {"session_id": session_id, **session_memory_store.load(session_id)}


@app.get("/v1/observability/events")
async def get_observability_events(limit: int = Query(default=100, ge=1, le=1000)):
    return {"events": metrics_recorder.load_events(limit=limit)}


@app.get("/v1/observability/summary")
async def get_observability_summary():
    return metrics_recorder.summary()


def execute_assistant_run(
    question: str,
    session_id: str | None,
    review_policy: str,
    on_stage=None,
):
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
    if on_stage:
        flow.kickoff_stepwise(review_policy=normalized_review_policy, on_stage=on_stage)
    else:
        flow.kickoff(review_policy=normalized_review_policy)

    task = flow.build_review_task()

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


def task_to_response(task, started_at: float):
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
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def derive_export_title(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"(?i)\bpdf\b", "", text)
    text = re.sub(r"(请|帮我|帮忙|把|将|内容|回答|结果|最近一次对话|最近的对话)", "", text)
    text = re.sub(r"(保存为?|导出为?|生成|输出|打印)", "", text)
    text = re.sub(r"(总结|概括|整理)", "", text)
    text = re.sub(r"[，,。.!！?？；;：:]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_")
    return text[:40] or "知识问答记录"


def build_export_content(title: str, answer_payload, answer_text: str) -> str:
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
