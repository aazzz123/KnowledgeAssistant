import hashlib
import re
from pathlib import Path
from typing import Dict, Iterable, List

import chromadb
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage

from config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DIR,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
)
from retrieval.keyword_index import build_keyword_records_with_metadata, save_keyword_records
from retrieval.search_service import get_embeddings
from security.file_sandbox import resolve_sandbox_path


TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")
SECTION_PATTERN = re.compile(r"(?m)^\s*(#{1,6}\s+.+|[一二三四五六七八九十]+[、.．].+|\d+(?:\.\d+)+\s+.+)\s*$")
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")


def approximate_token_count(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def normalize_text(text: str) -> str:
    # 这里先做一次粗清洗，目标不是完美排版，而是把后面的分段和切块尽量稳定下来。
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?<!\n)([一二三四五六七八九十]+[、.．])", r"\n\1", text)
    return text.strip()


def iter_document_pages(path: Path) -> List[Dict[str, str]]:
    if path.suffix.lower() in {".txt", ".md"}:
        return [{"page": "", "text": path.read_text(encoding="utf-8")}]

    with path.open("rb") as handle:
        page_count = sum(1 for _ in PDFPage.get_pages(handle))

    pages = []
    for page_index in range(page_count):
        pages.append(
            {
                "page": str(page_index + 1),
                "text": extract_text(str(path), page_numbers=[page_index]),
            }
        )
    return pages


def extract_document_metadata(path: Path, pages: List[Dict[str, str]]) -> Dict[str, str]:
    page_text = " ".join(page.get("text", "") for page in pages)
    normalized = normalize_text(page_text)
    first_line = next((line.strip() for line in normalized.splitlines() if line.strip()), "")
    year_match = YEAR_PATTERN.search(normalized)
    title = first_line if first_line and len(first_line) <= 80 else path.stem
    if not title:
        title = path.stem
    document_hash = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:10]
    return {
        "document_id": f"{path.stem}-{document_hash}",
        "title": title,
        "year": year_match.group(0) if year_match else "",
        "source": str(path.resolve()),
    }


def extract_paragraphs(path: Path) -> List[Dict[str, str]]:
    path = resolve_sandbox_path(path)
    pages = iter_document_pages(path)
    base_metadata = extract_document_metadata(path, pages)
    paragraphs: List[Dict[str, str]] = []
    current_section = ""
    paragraph_index = 0

    for page in pages:
        normalized = normalize_text(page.get("text", ""))
        if not normalized:
            continue
        # 把潜在标题前后强行打断，后面 section 边界就更容易保住。
        normalized = SECTION_PATTERN.sub(lambda match: f"\n{match.group(0).strip()}\n", normalized)
        blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            heading = lines[0]
            if SECTION_PATTERN.match(heading):
                current_section = heading
                body = "\n".join(lines[1:]).strip()
                if not body:
                    continue
                text = body
            else:
                text = "\n".join(lines).strip()

            paragraphs.append(
                {
                    **base_metadata,
                    "section": current_section,
                    "page": page.get("page", ""),
                    "paragraph_id": str(paragraph_index),
                    "text": text,
                }
            )
            paragraph_index += 1

    return paragraphs


def chunk_paragraphs(
    paragraphs: List[Dict[str, str]],
    chunk_size_tokens: int = CHUNK_SIZE_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> List[Dict[str, Dict[str, str]]]:
    chunks: List[Dict[str, Dict[str, str]]] = []
    current: List[Dict[str, str]] = []
    current_tokens = 0
    chunk_index = 0

    def emit_chunk(paragraph_group: List[Dict[str, str]]):
        nonlocal chunk_index
        if not paragraph_group:
            return
        text = "\n\n".join(item["text"] for item in paragraph_group if item.get("text"))
        if not text.strip():
            return
        metadata = {
            "document_id": paragraph_group[0].get("document_id", ""),
            "title": paragraph_group[0].get("title", ""),
            "year": paragraph_group[0].get("year", ""),
            "section": paragraph_group[0].get("section", ""),
            "page": paragraph_group[0].get("page", ""),
            "paragraph_range": f"{paragraph_group[0].get('paragraph_id', '')}-{paragraph_group[-1].get('paragraph_id', '')}",
            "source": paragraph_group[0].get("source", ""),
            "chunk_index": chunk_index,
        }
        chunks.append({"text": text, "metadata": metadata})
        chunk_index += 1

    for paragraph in paragraphs:
        paragraph_tokens = max(1, approximate_token_count(paragraph.get("text", "")))
        current_section = current[0].get("section", "") if current else ""
        next_section = paragraph.get("section", "")
        if current and next_section != current_section:
            # section 一旦变了，优先断块，避免一个 chunk 跨太多章节导致引用不清楚。
            emit_chunk(current)
            current = []
            current_tokens = 0

        if current and current_tokens + paragraph_tokens > chunk_size_tokens:
            emit_chunk(current)
            overlap_group: List[Dict[str, str]] = []
            overlap_count = 0
            # overlap 直接回捞末尾几个段落，检索时能少一点“刚好卡在边界上”的丢信息问题。
            for previous in reversed(current):
                overlap_group.insert(0, previous)
                overlap_count += max(1, approximate_token_count(previous.get("text", "")))
                if overlap_count >= overlap_tokens:
                    break
            current = overlap_group[:]
            current_tokens = sum(approximate_token_count(item.get("text", "")) for item in current)

        current.append(paragraph)
        current_tokens += paragraph_tokens

    emit_chunk(current)
    return chunks


def ingest_files(paths: Iterable[Path], collection_name: str = CHROMA_COLLECTION_NAME) -> int:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(name=collection_name)

    added = 0
    for path in paths:
        paragraphs = extract_paragraphs(path)
        chunks = chunk_paragraphs(paragraphs)
        if not chunks:
            continue

        # 关键词索引和向量库一起写，后面混合检索直接复用这两份数据。
        save_keyword_records(build_keyword_records_with_metadata(chunks))
        embeddings = get_embeddings([item["text"] for item in chunks])
        if not embeddings:
            continue

        ids = [stable_chunk_id(Path(item["metadata"]["source"]), item["metadata"]["chunk_index"]) for item in chunks]
        metadatas = [item["metadata"] for item in chunks]
        documents = [item["text"] for item in chunks]
        collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        added += len(chunks)

    return added


def stable_chunk_id(path: Path, chunk_index: int) -> str:
    raw = f"{path.resolve()}::{chunk_index}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()
