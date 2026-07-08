"""检索服务，负责向量召回、关键词召回、混合重排和证据格式化。"""

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Dict, List
from urllib.parse import urlparse

import chromadb
from openai import APIStatusError, OpenAI

from cache.redis_cache import redis_cache
from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DIR,
    EMBEDDING_API_BASE,
    EMBEDDING_API_KEY,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL_NAME,
    HYBRID_KEYWORD_WEIGHT,
    HYBRID_VECTOR_WEIGHT,
    KEYWORD_TOP_K,
    QUERY_CACHE_TTL_SECONDS,
    RERANK_CACHE_TTL_SECONDS,
    RERANK_KEYWORD_WEIGHT,
    RERANK_SOURCE_WEIGHT,
    RETRIEVAL_TOP_K,
)
from models.schemas import EvidenceItem, EvidenceMetadata
from observability.metrics import metrics_recorder
from retrieval.keyword_index import keyword_search, tokenize
from retrieval.query_dictionary import query_dictionary


logger = logging.getLogger(__name__)


@dataclass
class RetrievalCandidate:
    """统一表示候选证据，方便做向量 / 关键词融合和重排。"""

    key: str
    document: str
    metadata: Dict[str, str]
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0

    @property
    def hybrid_score(self) -> float:
        """按固定权重计算融合分。"""
        return (
            self.vector_score * HYBRID_VECTOR_WEIGHT
            + self.keyword_score * HYBRID_KEYWORD_WEIGHT
        )

    def to_dict(self):
        """转成可缓存的普通字典。"""
        return {
            "key": self.key,
            "document": self.document,
            "metadata": self.metadata,
            "vector_score": self.vector_score,
            "keyword_score": self.keyword_score,
            "rerank_score": self.rerank_score,
        }

    @classmethod
    def from_dict(cls, data):
        """从缓存结果恢复候选对象。"""
        return cls(**data)


@dataclass
class SearchResult:
    """检索阶段最终返回给工作流的结果结构。"""

    evidence: List[EvidenceItem]
    rendered_context: str
    metrics: Dict[str, float]
    expanded_query: str
    dictionary_hits: List[Dict[str, str]]


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """调用兼容 OpenAI 的 embedding 接口，返回文本向量。"""
    if not EMBEDDING_API_KEY:
        logger.warning("EMBEDDING_API_KEY is empty; retrieval will return no results.")
        return []
    if not texts:
        return []

    parsed_url = urlparse(EMBEDDING_API_BASE)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError(
            "EMBEDDING_API_BASE must be a valid URL, for example "
            "'http://localhost:3000/v1' or 'https://api.openai.com/v1'. "
            f"Current value: {EMBEDDING_API_BASE!r}"
        )

    client = OpenAI(base_url=EMBEDDING_API_BASE, api_key=EMBEDDING_API_KEY)
    batch_size = max(1, EMBEDDING_BATCH_SIZE)
    embeddings: List[List[float]] = []

    # 这里分批请求，主要是为了兼容上游对请求体大小比较敏感的情况。
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            response = client.embeddings.create(input=batch, model=EMBEDDING_MODEL_NAME)
        except APIStatusError as exc:
            raise RuntimeError(build_embedding_error_message(exc, start, batch, len(texts))) from exc
        except AttributeError as exc:
            raise RuntimeError(
                "Embedding API returned a non-OpenAI-compatible response. "
                "The /v1/embeddings endpoint should return JSON like "
                "{'data': [{'embedding': [...]}]}. Check EMBEDDING_API_BASE, "
                "EMBEDDING_MODEL_NAME, and the OneAPI channel type."
            ) from exc

        embeddings.extend(item.embedding for item in response.data)

    return embeddings


class KnowledgeRetriever:
    """统一封装私有知识检索逻辑。"""

    def __init__(self, collection_name: str = CHROMA_COLLECTION_NAME):
        """初始化 Chroma 集合。"""
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = client.get_or_create_collection(name=collection_name)

    def _vector_candidates(self, query: str, top_k: int) -> List[RetrievalCandidate]:
        """执行向量召回，返回候选证据。"""
        embeddings = get_embeddings([query])
        if not embeddings:
            return []

        results = self.collection.query(
            query_embeddings=embeddings,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])

        candidates = []
        for index, document in enumerate(documents[0]):
            metadata = metadatas[0][index] if metadatas and metadatas[0] else {}
            distance = distances[0][index] if distances and distances[0] else 1.0
            source = metadata.get("source", "unknown")
            chunk_index = int(metadata.get("chunk_index", index))
            key = f"{source}::{chunk_index}"
            candidates.append(
                RetrievalCandidate(
                    key=key,
                    document=document,
                    metadata=metadata,
                    # Chroma 返回的是距离，这里统一翻成“越大越相关”的分数，后面融合时更顺手。
                    vector_score=1 / (1 + max(distance, 0)),
                )
            )
        return candidates

    def _keyword_candidates(self, query: str, top_k: int) -> List[RetrievalCandidate]:
        """执行关键词召回，返回候选证据。"""
        results = keyword_search(query, top_k=top_k)
        if not results:
            return []

        max_score = max(item.get("bm25_score", item.get("keyword_score", 0)) for item in results) or 1
        candidates = []
        for item in results:
            metadata = item.get("metadata", {})
            source = item.get("source", "unknown")
            chunk_index = int(item.get("chunk_index", 0))
            key = f"{source}::{chunk_index}"
            candidates.append(
                RetrievalCandidate(
                    key=key,
                    document=item.get("document", ""),
                    metadata=metadata,
                    keyword_score=item.get("bm25_score", item.get("keyword_score", 0)) / max_score,
                )
            )
        return candidates

    def search(self, query: str, top_k: int = RETRIEVAL_TOP_K) -> SearchResult:
        """执行完整检索：词典扩展、双路召回、重排、缓存和证据格式化。"""
        started_at = time.perf_counter()
        expanded_query, dictionary_hits = query_dictionary.expand_query(query)
        cache_key = retrieval_cache_key(expanded_query, top_k)
        cached = redis_cache.get_json(cache_key)
        if cached:
            metrics_recorder.record(
                "retrieval_cache_hit",
                query=query,
                expanded_query=expanded_query,
                top_k=top_k,
                latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
            return SearchResult(
                evidence=[EvidenceItem(**item) for item in cached.get("evidence", [])],
                rendered_context=cached.get("text", ""),
                metrics=cached.get("metrics", {}),
                expanded_query=expanded_query,
                dictionary_hits=cached.get("dictionary_hits", []),
            )

        vector_candidates = []
        vector_error = ""
        try:
            vector_candidates = self._vector_candidates(expanded_query, top_k=top_k)
        except Exception as exc:
            vector_error = str(exc)
            logger.warning("Vector retrieval failed, falling back to keyword retrieval: %s", exc)

        keyword_candidates = self._keyword_candidates(expanded_query, top_k=KEYWORD_TOP_K)

        merged = {}
        # 向量召回和 BM25 命中的可能是同一个 chunk，这里先按稳定 key 合并再重排。
        for candidate in vector_candidates + keyword_candidates:
            existing = merged.get(candidate.key)
            if existing:
                existing.vector_score = max(existing.vector_score, candidate.vector_score)
                existing.keyword_score = max(existing.keyword_score, candidate.keyword_score)
            else:
                merged[candidate.key] = candidate

        rerank_cache = redis_cache.get_json(rerank_cache_key(expanded_query, top_k))
        if rerank_cache:
            ranked = [RetrievalCandidate.from_dict(item) for item in rerank_cache.get("candidates", [])]
        else:
            # query 用原始问法做 overlap，expanded_query 只负责召回，避免扩展词把重排结果带偏。
            ranked = rerank_candidates(query, list(merged.values()))
            redis_cache.set_json(
                rerank_cache_key(expanded_query, top_k),
                {"candidates": [candidate.to_dict() for candidate in ranked]},
                ttl_seconds=RERANK_CACHE_TTL_SECONDS,
            )

        selected = ranked[:top_k]
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        evidence_items = [candidate_to_evidence(candidate) for candidate in selected]
        metrics = build_metrics(selected)
        metrics_recorder.record(
            "retrieval",
            query=query,
            expanded_query=expanded_query,
            dictionary_hits=[
                {
                    "canonical": hit.canonical,
                    "matched": hit.matched,
                    "aliases": hit.aliases,
                }
                for hit in dictionary_hits
            ],
            top_k=top_k,
            vector_count=len(vector_candidates),
            bm25_count=len(keyword_candidates),
            hybrid_count=len(selected),
            latency_ms=latency_ms,
            vector_error=vector_error,
            review_metrics=metrics,
        )

        if not selected:
            return SearchResult(
                evidence=[],
                rendered_context="No relevant knowledge chunks were found.",
                metrics=metrics,
                expanded_query=expanded_query,
                dictionary_hits=[hit.__dict__ for hit in dictionary_hits],
            )

        text = render_evidence_context(evidence_items)
        redis_cache.set_json(
            cache_key,
            {
                "text": text,
                "expanded_query": expanded_query,
                "evidence": [item.model_dump() for item in evidence_items],
                "metrics": metrics,
                "dictionary_hits": [hit.__dict__ for hit in dictionary_hits],
            },
            ttl_seconds=QUERY_CACHE_TTL_SECONDS,
        )
        return SearchResult(
            evidence=evidence_items,
            rendered_context=text,
            metrics=metrics,
            expanded_query=expanded_query,
            dictionary_hits=[hit.__dict__ for hit in dictionary_hits],
        )


def search_knowledge(query: str, top_k: int = RETRIEVAL_TOP_K) -> SearchResult:
    """给外部统一暴露的检索入口。"""
    return KnowledgeRetriever().search(query, top_k=top_k)


def rerank_candidates(query: str, candidates: List[RetrievalCandidate]) -> List[RetrievalCandidate]:
    """用关键词 overlap 和来源命中对候选证据做轻量重排。"""
    query_terms = set(tokenize(query))
    for candidate in candidates:
        doc_terms = set(tokenize(candidate.document))
        overlap = len(query_terms & doc_terms) / max(len(query_terms), 1)
        source_text = str(candidate.metadata.get("source", "")).lower()
        source_bonus = 1.0 if any(term in source_text for term in query_terms) else 0.0
        candidate.rerank_score = (
            candidate.hybrid_score
            + overlap * RERANK_KEYWORD_WEIGHT
            + source_bonus * RERANK_SOURCE_WEIGHT
        )
    return sorted(candidates, key=lambda item: item.rerank_score, reverse=True)


def candidate_to_evidence(candidate: RetrievalCandidate) -> EvidenceItem:
    """把候选对象转换成前后端统一使用的证据结构。"""
    metadata = EvidenceMetadata(
        document_id=str(candidate.metadata.get("document_id", "")),
        title=str(candidate.metadata.get("title", "")),
        year=str(candidate.metadata.get("year", "")),
        section=str(candidate.metadata.get("section", "")),
        page=str(candidate.metadata.get("page", "")),
        paragraph_range=str(candidate.metadata.get("paragraph_range", "")),
        source=str(candidate.metadata.get("source", "")),
        chunk_index=int(candidate.metadata.get("chunk_index", 0)),
    )
    return EvidenceItem(
        evidence_id=candidate.key,
        text=candidate.document,
        metadata=metadata,
        dense_score=round(candidate.vector_score, 4),
        bm25_score=round(candidate.keyword_score, 4),
        hybrid_score=round(candidate.hybrid_score, 4),
        rerank_score=round(candidate.rerank_score, 4),
    )


def render_evidence_context(evidence: List[EvidenceItem]) -> str:
    """把证据拼成适合喂给大模型的上下文文本。"""
    if not evidence:
        return "No relevant knowledge chunks were found."

    # 返回给大模型的上下文刻意保留元数据和分数，后面答复里更容易做引用和自检。
    chunks = []
    for index, item in enumerate(evidence, start=1):
        metadata = item.metadata
        chunks.append(
            "\n".join(
                [
                    f"[{index}] document_id={metadata.document_id or ''} title={metadata.title or ''}",
                    f"section={metadata.section or ''} page={metadata.page or ''} paragraph_range={metadata.paragraph_range or ''}",
                    (
                        "scores="
                        f"rerank:{item.rerank_score:.4f}, "
                        f"hybrid:{item.hybrid_score:.4f}, "
                        f"dense:{item.dense_score:.4f}, "
                        f"bm25:{item.bm25_score:.4f}"
                    ),
                    item.text,
                ]
            )
        )
    return "\n\n".join(chunks)


def build_metrics(candidates: List[RetrievalCandidate]) -> Dict[str, float]:
    """生成给审核规则使用的关键检索指标。"""
    if not candidates:
        return {
            "top_evidence_count": 0,
            "max_rerank_score": 0.0,
            "source_count": 0,
            "dominant_source_ratio": 0.0,
        }

    source_counter: Dict[str, int] = {}
    # 审核规则只看 Top5，避免长尾证据把“来源是否一致”这个判断稀释掉。
    for candidate in candidates[:5]:
        source = candidate.metadata.get("document_id") or candidate.metadata.get("source") or "unknown"
        source_counter[source] = source_counter.get(source, 0) + 1
    dominant_source = max(source_counter.values()) if source_counter else 0
    return {
        "top_evidence_count": len(candidates[:5]),
        "max_rerank_score": round(max(candidate.rerank_score for candidate in candidates), 4),
        "source_count": len(source_counter),
        "dominant_source_ratio": round(dominant_source / max(len(candidates[:5]), 1), 4),
    }


def retrieval_cache_key(query: str, top_k: int) -> str:
    """生成检索缓存 key。"""
    raw = f"{query}::{top_k}::{CHROMA_COLLECTION_NAME}".encode("utf-8")
    return f"retrieval:{hashlib.sha1(raw).hexdigest()}"


def rerank_cache_key(query: str, top_k: int) -> str:
    """生成重排缓存 key。"""
    raw = f"{query}::{top_k}::{CHROMA_COLLECTION_NAME}::rerank".encode("utf-8")
    return f"rerank:{hashlib.sha1(raw).hexdigest()}"


def build_embedding_error_message(
    exc: APIStatusError,
    start_index: int,
    batch: List[str],
    total_count: int,
) -> str:
    """拼出更容易排查的 embedding 上游错误信息。"""
    status_code = getattr(exc, "status_code", "unknown")
    response_text = ""
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            response_text = response.text
        except Exception:
            response_text = str(response)
    response_text = (response_text or "").strip()
    if len(response_text) > 500:
        response_text = response_text[:500] + "...(truncated)"

    sample_preview = batch[0][:120].replace("\n", " ") if batch else ""
    return (
        "Embedding API returned an error. "
        f"status_code={status_code}, model={EMBEDDING_MODEL_NAME}, "
        f"base_url={EMBEDDING_API_BASE}, batch_start={start_index}, "
        f"batch_size={len(batch)}, total_texts={total_count}, "
        f"sample_preview={sample_preview!r}, upstream_response={response_text!r}. "
        "Check whether the embedding model is enabled in OneAPI, whether the channel "
        "supports /v1/embeddings, and whether the batch size is too large."
    )
