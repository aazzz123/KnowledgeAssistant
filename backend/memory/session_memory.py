import json
import threading
from pathlib import Path
from typing import Dict, List

import chromadb

from cache.redis_cache import redis_cache
from config import CHROMA_DIR, LONG_MEMORY_COLLECTION_NAME, SESSION_CACHE_TTL_SECONDS
from models.schemas import MemoryRecord, SessionMemory
from retrieval.search_service import get_embeddings


class SessionMemoryStore:
    """Session memory stored in Redis/local JSON plus vectorized long-term recall."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.long_collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
            name=LONG_MEMORY_COLLECTION_NAME
        )

    def _safe_id(self, session_id: str) -> str:
        return "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))

    def _short_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{self._safe_id(session_id)}.short.json"

    def _long_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{self._safe_id(session_id)}.long.json"

    def _path(self, session_id: str) -> Path:
        return self.storage_dir / f"{self._safe_id(session_id)}.json"

    def _load_list_path(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, list) else []

    def _load_dict_path(self, path: Path) -> Dict:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {}

    def _write_path(self, path: Path, payload) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    def load(self, session_id: str) -> Dict:
        cached = redis_cache.get_json(self._state_cache_key(session_id))
        if cached is not None:
            return cached

        state = self._load_dict_path(self._short_path(session_id))
        if state:
            state.setdefault("session_id", session_id)
            state.setdefault("current_topic", "")
            state.setdefault("recent_questions", [])
            state.setdefault("confirmed_answers", [])
            state.setdefault("summary_context", "")
            state.setdefault("short_term", [])
            state.setdefault("long_term", self._load_list_path(self._long_path(session_id)))
            redis_cache.set_json(
                self._state_cache_key(session_id),
                state,
                ttl_seconds=SESSION_CACHE_TTL_SECONDS,
            )
            return state

        legacy_short = self._load_list_path(self._short_path(session_id)) or self._load_list_path(
            self._path(session_id)
        )
        long_term = self._load_list_path(self._long_path(session_id))
        state = SessionMemory(
            session_id=session_id,
            current_topic="",
            recent_questions=[item.get("question", "") for item in legacy_short if item.get("question")],
            confirmed_answers=[item.get("answer", "") for item in legacy_short if item.get("answer")],
            summary_context="",
            short_term=[MemoryRecord(**item).model_dump() for item in legacy_short] if legacy_short else [],
            long_term=long_term,
        ).model_dump()
        redis_cache.set_json(
            self._state_cache_key(session_id),
            state,
            ttl_seconds=SESSION_CACHE_TTL_SECONDS,
        )
        return state

    def append(self, session_id: str, record: MemoryRecord) -> None:
        with self._lock:
            state = self.load(session_id)
            short_records = state.get("short_term", [])
            short_records.append(record.model_dump())
            short_records = short_records[-8:]

            state["session_id"] = session_id
            state["short_term"] = short_records
            state["recent_questions"] = (state.get("recent_questions", []) + [record.question])[-8:]
            if record.confirmed and record.answer_payload and record.answer_payload.conclusion:
                state["confirmed_answers"] = (
                    state.get("confirmed_answers", []) + [record.answer_payload.conclusion]
                )[-5:]
            state["current_topic"] = infer_topic(state)
            state["summary_context"] = self._build_summary_context(short_records)

            long_records = state.get("long_term", [])
            long_record = self._to_long_term_record(record)
            long_records.append(long_record)
            state["long_term"] = long_records[-50:]

            redis_cache.set_json(
                self._state_cache_key(session_id),
                state,
                ttl_seconds=SESSION_CACHE_TTL_SECONDS,
            )
            self._write_path(self._short_path(session_id), state)
            self._write_path(self._long_path(session_id), state["long_term"])
            self._upsert_long_memory(session_id, long_record)

    def summarize_recent(self, session_id: str, query: str = "", limit: int = 3) -> str:
        state = self.load(session_id)
        short_records = state.get("short_term", [])[-limit:]
        long_records = self.semantic_recall(session_id, query=query, limit=limit)
        if not long_records:
            long_records = state.get("long_term", [])[-limit:]
        if not short_records and not long_records:
            return "No previous short-term or long-term memory for this session."

        chunks = []
        if state.get("current_topic"):
            chunks.append(f"Current topic: {state['current_topic']}")
        if state.get("summary_context"):
            chunks.append(f"Session summary:\n{state['summary_context']}")
        for index, item in enumerate(short_records, start=1):
            chunks.append(
                "\n".join(
                    [
                        f"Short-term memory #{index}",
                        f"Question: {item.get('question', '')}",
                        f"Feedback: {item.get('feedback', '')}",
                        f"Final answer: {str(item.get('answer', '') or item.get('draft', ''))[:800]}",
                    ]
                )
            )
        for index, item in enumerate(long_records, start=1):
            chunks.append(
                "\n".join(
                    [
                        f"Long-term memory #{index}",
                        f"Question: {item.get('question', '')}",
                        f"Summary: {item.get('summary', '')}",
                    ]
                )
            )
        return "\n\n".join(chunks)

    def semantic_recall(self, session_id: str, query: str, limit: int = 3) -> List[Dict]:
        if not query:
            return []
        try:
            embeddings = get_embeddings([query])
            if not embeddings:
                return []
            result = self.long_collection.query(
                query_embeddings=embeddings,
                n_results=limit,
                where={"session_id": session_id},
                include=["metadatas", "documents"],
            )
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            records = []
            for index, document in enumerate(documents):
                metadata = metadatas[index] if index < len(metadatas) else {}
                records.append(
                    {
                        "task_id": metadata.get("task_id", ""),
                        "question": metadata.get("question", ""),
                        "summary": document,
                        "feedback": metadata.get("feedback", ""),
                    }
                )
            return records
        except Exception:
            return []

    def _to_long_term_record(self, record: MemoryRecord) -> Dict:
        return {
            "task_id": record.task_id,
            "question": record.question,
            "summary": self._compact_text(record.answer or record.draft),
            "feedback": record.feedback,
            "conclusion": (
                record.answer_payload.conclusion
                if record.answer_payload and record.answer_payload.conclusion
                else ""
            ),
        }

    def _compact_text(self, text: str, limit: int = 500) -> str:
        clean = " ".join(text.split())
        return clean[:limit]

    def _build_summary_context(self, records: List[Dict], limit: int = 4) -> str:
        snippets = []
        for item in records[-limit:]:
            snippets.append(
                f"Q: {item.get('question', '')}\nA: {self._compact_text(item.get('answer', '') or item.get('draft', ''), 220)}"
            )
        return "\n\n".join(snippets)

    def _upsert_long_memory(self, session_id: str, long_record: Dict) -> None:
        summary = long_record.get("summary", "")
        if not summary:
            return
        try:
            embeddings = get_embeddings([summary])
            if not embeddings:
                return
            memory_id = f"{session_id}:{long_record.get('task_id')}"
            self.long_collection.upsert(
                ids=[memory_id],
                documents=[summary],
                embeddings=embeddings,
                metadatas=[
                    {
                        "session_id": session_id,
                        "task_id": long_record.get("task_id", ""),
                        "question": long_record.get("question", ""),
                        "feedback": long_record.get("feedback", ""),
                    }
                ],
            )
        except Exception:
            return

    def _state_cache_key(self, session_id: str) -> str:
        return f"session:{self._safe_id(session_id)}:state"


def infer_topic(state: Dict) -> str:
    recent_questions = [item for item in state.get("recent_questions", []) if item]
    if not recent_questions:
        return ""
    return recent_questions[-1][:80]
