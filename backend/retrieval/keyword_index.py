import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

from config import KEYWORD_INDEX_PATH


def tokenize(text: str) -> List[str]:
    ascii_terms = re.findall(r"[A-Za-z0-9_]+", text.lower())
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    chinese_bigrams = [
        "".join(chinese_chars[index : index + 2])
        for index in range(max(0, len(chinese_chars) - 1))
    ]
    return ascii_terms + chinese_chars + chinese_bigrams


def load_keyword_index(path: Path = KEYWORD_INDEX_PATH) -> List[Dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_keyword_records(records: Iterable[Dict], path: Path = KEYWORD_INDEX_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_keyword_index(path)
    existing_keys = {
        f"{item.get('source')}::{item.get('chunk_index')}" for item in existing
    }

    merged = existing[:]
    for record in records:
        key = f"{record.get('source')}::{record.get('chunk_index')}"
        if key not in existing_keys:
            merged.append(record)
            existing_keys.add(key)

    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def build_keyword_records(chunks: List[str], source: Path) -> List[Dict]:
    return build_keyword_records_with_metadata(
        [
            {
                "text": chunk,
                "metadata": {
                    "source": str(source),
                    "chunk_index": index,
                    "document_id": "",
                    "title": source.stem,
                    "year": "",
                    "section": "",
                    "page": "",
                    "paragraph_range": "",
                },
            }
            for index, chunk in enumerate(chunks)
        ]
    )


def build_keyword_records_with_metadata(chunks: List[Dict]) -> List[Dict]:
    records = []
    for index, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        metadata = chunk.get("metadata", {})
        tokens = tokenize(text)
        records.append(
            {
                "source": metadata.get("source", ""),
                "chunk_index": int(metadata.get("chunk_index", index)),
                "document": text,
                "terms": Counter(tokens),
                "doc_len": len(tokens),
                "metadata": metadata,
            }
        )
    return records


def bm25_search(query: str, top_k: int = 5, k1: float = 1.5, b: float = 0.75) -> List[Dict]:
    records = load_keyword_index()
    if not records:
        return []

    query_terms = tokenize(query)
    query_counts = Counter(query_terms)
    if not query_counts:
        return []

    doc_freq = Counter()
    for record in records:
        doc_freq.update(record.get("terms", {}).keys())

    total_docs = len(records)
    avg_doc_len = sum(record.get("doc_len", 0) for record in records) / max(total_docs, 1)
    scored = []
    for record in records:
        terms = record.get("terms", {})
        doc_len = record.get("doc_len", sum(terms.values())) or 1
        score = 0.0
        for term, query_count in query_counts.items():
            term_freq = terms.get(term, 0)
            if not term_freq:
                continue
            idf = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            numerator = term_freq * (k1 + 1)
            denominator = term_freq + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
            score += query_count * idf * numerator / denominator
        if score > 0:
            scored.append({**record, "bm25_score": score})

    scored.sort(key=lambda item: item["bm25_score"], reverse=True)
    return scored[:top_k]


def keyword_search(query: str, top_k: int = 5) -> List[Dict]:
    return bm25_search(query, top_k=top_k)
