"""LangGraph 工作流定义，负责把检索、记忆、起草和审核串起来。"""

import json
import uuid
from typing import Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from memory.session_memory import SessionMemoryStore
from models.schemas import MemoryRecord, TaskState
from orchestration.prompt_chains import KnowledgeAssistantChains, render_answer_payload
from review.review_policy import assess_review_need, summarize_assessment
from retrieval.search_service import search_knowledge
from tools.save_pdf_tool import save_text_to_pdf


class AssistantGraphState(TypedDict, total=False):
    """图状态里会在各个节点之间流转的字段。"""

    task_id: str
    session_id: str
    question: str
    review_policy: str
    retrieved_context: str
    retrieved_evidence: list
    review_metrics: dict
    memory_context: str
    draft: str
    draft_payload: dict
    review_decision: str
    review_reason: str


class KnowledgeAssistantFlow:
    """封装整个知识问答流程，供接口层按同步或流式方式调用。"""

    def __init__(self, llm, memory: SessionMemoryStore, question: str, session_id: str):
        """初始化一次问答任务需要的上下文。"""
        self.llm = llm
        self.memory = memory
        self.question = question
        self.session_id = session_id
        self.task_id = str(uuid.uuid4())
        self.retrieved_context = ""
        self.retrieved_evidence = []
        self.review_metrics = {}
        self.draft = ""
        self.draft_payload = None
        self.review_decision = "unknown"
        self.review_reason = ""
        self._graph = self._build_graph().compile()

    def _build_graph(self) -> StateGraph:
        """定义图结构：检索 -> 记忆 -> 起草 -> 审核。"""
        graph = StateGraph(AssistantGraphState)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("load_memory", self._load_memory)
        graph.add_node("generate_draft", self._generate_draft)
        graph.add_node("decide_review", self._decide_review)
        graph.add_edge(START, "retrieve_context")
        graph.add_edge("retrieve_context", "load_memory")
        graph.add_edge("load_memory", "generate_draft")
        graph.add_edge("generate_draft", "decide_review")
        graph.add_edge("decide_review", END)
        return graph

    def _retrieve_context(self, state: AssistantGraphState) -> AssistantGraphState:
        """执行检索并把证据整理成图状态。"""
        result = search_knowledge(state["question"])
        return {
            "retrieved_context": result.rendered_context,
            "retrieved_evidence": [item.model_dump() for item in result.evidence],
            "review_metrics": result.metrics,
        }

    def _load_memory(self, state: AssistantGraphState) -> AssistantGraphState:
        """补充最近会话记忆，给后面的答案生成提供上下文。"""
        return {
            "memory_context": self.memory.summarize_recent(
                state["session_id"], query=state["question"]
            )
        }

    def _generate_draft(
        self,
        state: AssistantGraphState,
        on_conclusion_delta: Optional[Callable[[str], None]] = None,
    ) -> AssistantGraphState:
        """生成结构化草稿，必要时把结论做流式增量输出。"""
        draft_payload = KnowledgeAssistantChains(self.llm).draft(
            question=state["question"],
            retrieved_context=state["retrieved_context"],
            retrieved_evidence_json=json.dumps(
                state.get("retrieved_evidence", []), ensure_ascii=False, indent=2
            ),
            memory_context=state["memory_context"],
            on_conclusion_delta=on_conclusion_delta,
        )
        return {
            "draft_payload": draft_payload.model_dump(),
            "draft": render_answer_payload(draft_payload),
        }

    def _decide_review(self, state: AssistantGraphState) -> AssistantGraphState:
        """结合规则和模型解释，决定是否进入人工审核。"""
        if state["review_policy"] == "always":
            return {
                "review_decision": "REVIEW_REQUIRED",
                "review_reason": "Review policy is always.",
            }

        if state["review_policy"] == "never":
            return {
                "review_decision": "AUTO_APPROVED",
                "review_reason": "Review policy is never.",
            }

        assessment = assess_review_need(
            question=state["question"],
            evidence=state.get("retrieved_evidence", []),
            metrics=state.get("review_metrics", {}),
        )
        rule_summary = summarize_assessment(assessment)

        # 审核判断优先按代码规则卡底线，模型这里只负责补充解释，不反过来推翻规则结果。
        raw_decision = KnowledgeAssistantChains(self.llm).explain_review(
            question=state["question"],
            retrieved_context=state["retrieved_context"],
            draft=state["draft"],
            review_policy=state["review_policy"],
            rule_summary=rule_summary,
            review_metrics_json=json.dumps(state.get("review_metrics", {}), ensure_ascii=False),
        )
        model_decision, model_reason = parse_review_decision(raw_decision)
        review_decision = "REVIEW_REQUIRED" if assessment.requires_human_review else model_decision
        review_reason = f"Rules: {rule_summary} Model: {model_reason}".strip()
        return {
            "review_decision": review_decision,
            "review_reason": review_reason,
        }

    def kickoff(self, review_policy: str):
        """同步跑完整张图，并把结果回填到实例属性。"""
        result = self._graph.invoke(
            {
                "task_id": self.task_id,
                "session_id": self.session_id,
                "question": self.question,
                "review_policy": review_policy,
            }
        )
        self.retrieved_context = result.get("retrieved_context", "")
        self.retrieved_evidence = result.get("retrieved_evidence", [])
        self.review_metrics = result.get("review_metrics", {})
        self.draft = result.get("draft", "")
        self.draft_payload = result.get("draft_payload")
        self.review_decision = result.get("review_decision", "unknown")
        self.review_reason = result.get("review_reason", "")
        return result

    def kickoff_stepwise(
        self,
        review_policy: str,
        on_stage: Optional[Callable[[str, dict], None]] = None,
    ):
        """按阶段执行流程，适合给 SSE 持续推送事件。"""
        state: AssistantGraphState = {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "question": self.question,
            "review_policy": review_policy,
        }

        if on_stage:
            on_stage("task_started", {"task_id": self.task_id, "session_id": self.session_id})

        state.update(self._retrieve_context(state))
        if on_stage:
            on_stage(
                "retrieval_completed",
                {
                    "retrieved_context": state.get("retrieved_context", ""),
                    "retrieved_evidence": state.get("retrieved_evidence", []),
                    "review_metrics": state.get("review_metrics", {}),
                },
            )

        state.update(self._load_memory(state))
        if on_stage:
            on_stage("memory_loaded", {"memory_context": state.get("memory_context", "")})

        state.update(
            self._generate_draft(
                state,
                on_conclusion_delta=(
                    # 草稿流式输出时只推结论文本，等草稿完整后再把其他结构化字段一次性补齐。
                    lambda text: on_stage("draft_delta", {"text": text}) if on_stage else None
                ),
            )
        )
        if on_stage:
            on_stage(
                "draft_completed",
                {
                    "draft": state.get("draft", ""),
                    "draft_payload": state.get("draft_payload"),
                },
            )

        state.update(self._decide_review(state))
        if on_stage:
            on_stage(
                "review_decided",
                {
                    "review_decision": state.get("review_decision", "unknown"),
                    "review_reason": state.get("review_reason", ""),
                },
            )

        self.retrieved_context = state.get("retrieved_context", "")
        self.retrieved_evidence = state.get("retrieved_evidence", [])
        self.review_metrics = state.get("review_metrics", {})
        self.draft = state.get("draft", "")
        self.draft_payload = state.get("draft_payload")
        self.review_decision = state.get("review_decision", "unknown")
        self.review_reason = state.get("review_reason", "")
        return state

    def build_review_task(self) -> TaskState:
        """把当前流程状态收敛成一个可存储、可审核的任务对象。"""
        return TaskState(
            task_id=self.task_id,
            session_id=self.session_id,
            status="waiting_feedback",
            question=self.question,
            retrieved_context=self.retrieved_context,
            retrieved_evidence=self.retrieved_evidence,
            review_metrics=self.review_metrics,
            draft=self.draft,
            draft_payload=self.draft_payload,
            review_decision=self.review_decision,
            review_reason=self.review_reason,
        )


def parse_review_decision(raw_decision: str):
    """从模型返回文本里提取审核决策和原因。"""
    decision = "REVIEW_REQUIRED"
    reason = raw_decision.strip()
    for line in raw_decision.splitlines():
        upper_line = line.upper()
        if upper_line.startswith("DECISION:"):
            value = line.split(":", 1)[1].strip().upper()
            if value in {"REVIEW_REQUIRED", "AUTO_APPROVED"}:
                decision = value
        elif upper_line.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    return decision, reason


def finalize_with_feedback(
    llm,
    memory: SessionMemoryStore,
    task: TaskState,
    feedback: str,
    approved: bool,
    on_conclusion_delta: Optional[Callable[[str], None]] = None,
) -> TaskState:
    """结合人工审核意见重新定稿，并更新会话记忆与导出文件。"""
    memory_context = memory.summarize_recent(task.session_id, query=task.question)

    # 定稿阶段会把审核意见、检索证据和会话记忆重新拼起来，避免只是机械复用草稿。
    answer_payload = KnowledgeAssistantChains(llm).finalize(
        question=task.question,
        retrieved_context=task.retrieved_context,
        retrieved_evidence_json=json.dumps(
            [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in task.retrieved_evidence
            ],
            ensure_ascii=False,
            indent=2,
        ),
        draft_payload_json=json.dumps(
            task.draft_payload.model_dump()
            if hasattr(task.draft_payload, "model_dump")
            else task.draft_payload or {},
            ensure_ascii=False,
            indent=2,
        ),
        feedback=feedback,
        approved=approved,
        memory_context=memory_context,
        on_conclusion_delta=on_conclusion_delta,
    )
    answer = render_answer_payload(answer_payload)
    report_path = save_text_to_pdf(answer, filename=f"{task.task_id}.pdf")

    task.feedback = feedback
    task.approved = approved
    task.answer = answer
    task.answer_payload = answer_payload
    task.status = "completed"
    task.metadata["report_path"] = report_path

    memory.append(
        task.session_id,
        MemoryRecord(
            task_id=task.task_id,
            question=task.question,
            retrieved_context=task.retrieved_context,
            draft=task.draft,
            draft_payload=task.draft_payload,
            feedback=feedback,
            answer=answer,
            answer_payload=answer_payload,
            confirmed=True,
        ),
    )
    return task
