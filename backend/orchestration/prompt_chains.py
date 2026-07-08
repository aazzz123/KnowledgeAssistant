"""Prompt 链封装，负责把工作流输入组织成模型请求。"""

import json
import re
from typing import Any, Callable, Dict, Optional

from langchain_core.prompts import ChatPromptTemplate

from models.schemas import StructuredAnswerPayload
from orchestration.yaml_loader import load_yaml_config


class KnowledgeAssistantChains:
    """集中管理草稿生成、定稿和审核解释这几类模型调用。"""

    agents_config = load_yaml_config("config/agents.yaml")
    tasks_config = load_yaml_config("config/tasks.yaml")

    def __init__(self, llm):
        """保存当前流程要复用的模型实例。"""
        self.llm = llm

    def _build_system_prompt(self, agent_key: str) -> str:
        """根据 agent 配置拼出 system prompt。"""
        agent_config = self.agents_config[agent_key]
        return "\n".join(
            [
                f"Role: {agent_config['role']}",
                f"Goal: {agent_config['goal']}",
                f"Backstory: {agent_config['backstory']}",
            ]
        )

    def _invoke(self, agent_key: str, task_key: str, variables: dict) -> str:
        """发起一次普通文本调用。"""
        return self._invoke_with_stream(
            agent_key=agent_key,
            task_key=task_key,
            variables=variables,
        )

    def _invoke_with_stream(
        self,
        agent_key: str,
        task_key: str,
        variables: dict,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> str:
        """发起一次支持流式片段回调的调用。"""
        task_config = self.tasks_config[task_key]
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._build_system_prompt(agent_key)),
                (
                    "human",
                    "\n\n".join(
                        [
                            task_config["description"],
                            f"Expected output:\n{task_config['expected_output']}",
                        ]
                    ),
                ),
            ]
        )
        chain = prompt | self.llm
        if on_chunk is None:
            response = chain.invoke(variables)
            return getattr(response, "content", str(response)).strip()

        parts: list[str] = []
        # 有些模型会把 chunk 拆得很碎，这里先累加原始片段，再交给上层决定怎么消费。
        for chunk in chain.stream(variables):
            text = normalize_chunk_text(getattr(chunk, "content", chunk))
            if not text:
                continue
            parts.append(text)
            on_chunk(text)
        return "".join(parts).strip()

    def _invoke_json(
        self,
        agent_key: str,
        task_key: str,
        variables: dict,
        on_conclusion_delta: Optional[Callable[[str], None]] = None,
    ) -> StructuredAnswerPayload:
        """发起结构化 JSON 调用，并在需要时抽取流式结论。"""
        latest_conclusion = ""
        raw_parts: list[str] = []

        def handle_chunk(text: str):
            nonlocal latest_conclusion
            raw_parts.append(text)
            if on_conclusion_delta is None:
                return

            # 这里不等 JSON 完整闭合，先从半成品里尽量抠出 conclusion，前端才能看到真流式效果。
            partial_conclusion = extract_partial_json_string_field(
                "".join(raw_parts),
                "conclusion",
            )
            if partial_conclusion and partial_conclusion != latest_conclusion:
                latest_conclusion = partial_conclusion
                on_conclusion_delta(partial_conclusion)

        raw = self._invoke_with_stream(
            agent_key=agent_key,
            task_key=task_key,
            variables=variables,
            on_chunk=handle_chunk if on_conclusion_delta else None,
        )
        payload = parse_json_payload(raw)
        return StructuredAnswerPayload(
            conclusion=str(payload.get("conclusion", raw)).strip(),
            basis=ensure_string_list(payload.get("basis")),
            citations=ensure_string_list(payload.get("citations")),
            evidence_gaps=ensure_string_list(payload.get("evidence_gaps")),
            review_note=str(payload.get("review_note", "")).strip(),
        )

    def draft(
        self,
        question: str,
        retrieved_context: str,
        retrieved_evidence_json: str,
        memory_context: str,
        on_conclusion_delta: Optional[Callable[[str], None]] = None,
    ) -> StructuredAnswerPayload:
        """生成草稿答案。"""
        return self._invoke_json(
            agent_key="knowledge_analyst",
            task_key="draft_answer_task",
            variables={
                "question": question,
                "retrieved_context": retrieved_context,
                "retrieved_evidence_json": retrieved_evidence_json,
                "memory_context": memory_context,
            },
            on_conclusion_delta=on_conclusion_delta,
        )

    def finalize(
        self,
        question: str,
        retrieved_context: str,
        retrieved_evidence_json: str,
        draft_payload_json: str,
        feedback: str,
        approved: bool,
        memory_context: str,
        on_conclusion_delta: Optional[Callable[[str], None]] = None,
    ) -> StructuredAnswerPayload:
        """结合审核意见生成最终答案。"""
        return self._invoke_json(
            agent_key="final_report_writer",
            task_key="final_answer_task",
            variables={
                "question": question,
                "retrieved_context": retrieved_context,
                "retrieved_evidence_json": retrieved_evidence_json,
                "draft_payload_json": draft_payload_json,
                "feedback": feedback,
                "approved": approved,
                "memory_context": memory_context,
            },
            on_conclusion_delta=on_conclusion_delta,
        )

    def explain_review(
        self,
        question: str,
        retrieved_context: str,
        draft: str,
        review_policy: str,
        rule_summary: str,
        review_metrics_json: str,
    ) -> str:
        """让模型补一段审核解释，但不直接控制规则结果。"""
        return self._invoke(
            agent_key="review_decision_agent",
            task_key="review_decision_task",
            variables={
                "question": question,
                "retrieved_context": retrieved_context,
                "draft": draft,
                "review_policy": review_policy,
                "rule_summary": rule_summary,
                "review_metrics_json": review_metrics_json,
            },
        )


def parse_json_payload(raw: str) -> Dict[str, Any]:
    """把模型输出尽量解析成 JSON 对象。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    # 模型偶尔还是会跑偏，这里兜成一个最小可用结构，至少别把整条链路打断。
    return {"conclusion": raw, "basis": [], "citations": [], "evidence_gaps": [], "review_note": ""}


def ensure_string_list(value: Any) -> list[str]:
    """把模型返回值尽量规整成字符串列表。"""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    value_str = str(value).strip()
    return [value_str] if value_str else []


def normalize_chunk_text(content: Any) -> str:
    """把不同形态的流式片段统一转成字符串。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


def extract_partial_json_string_field(raw: str, field_name: str) -> str:
    """从半成品 JSON 字符串里尽量提取指定字段。"""
    pattern = rf'"{re.escape(field_name)}"\s*:\s*"(?P<value>(?:\\.|[^"])*)'
    match = re.search(pattern, raw, flags=re.DOTALL)
    if not match:
        return ""
    escaped = match.group("value")
    return decode_partial_json_string(escaped).strip()


def decode_partial_json_string(value: str) -> str:
    """宽松解码半截 JSON 字符串，优先保证前端能看到正常文字。"""
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        sanitized = value.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
        sanitized = re.sub(r"\\u[0-9a-fA-F]{0,3}$", "", sanitized)
        sanitized = re.sub(r"\\$", "", sanitized)
        return sanitized


def render_answer_payload(payload: StructuredAnswerPayload) -> str:
    """把结构化答案渲染成便于导出和调试的纯文本。"""
    lines = [
        "Conclusion:",
        payload.conclusion or "",
        "",
        "Basis:",
    ]
    lines.extend(f"- {item}" for item in payload.basis)
    lines.extend(["", "Citations:"])
    lines.extend(f"- {item}" for item in payload.citations)
    lines.extend(["", "Evidence Gaps:"])
    lines.extend(f"- {item}" for item in payload.evidence_gaps)
    lines.extend(["", "Review Note:", payload.review_note or ""])
    return "\n".join(lines).strip()
