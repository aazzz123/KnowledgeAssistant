import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_NAME = "KnowledgeAssistant"
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
MEMORY_DIR = DATA_DIR / "memory"
OBSERVABILITY_DIR = DATA_DIR / "observability"
REPORT_DIR = DATA_DIR / "reports"
CHROMA_DIR = DATA_DIR / "chroma"
KEYWORD_INDEX_PATH = DATA_DIR / "keyword_index.json"
OBSERVABILITY_EVENTS_PATH = OBSERVABILITY_DIR / "events.jsonl"
PROPRIETARY_DICTIONARY_PATH = BASE_DIR / "config" / "proprietary_dictionary.json"

for directory in (DATA_DIR, INPUT_DIR, MEMORY_DIR, OBSERVABILITY_DIR, REPORT_DIR, CHROMA_DIR):
    directory.mkdir(parents=True, exist_ok=True)


PORT = int(os.getenv("KNOWLEDGE_ASSISTANT_PORT", "8014"))

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

LLM_TYPE = os.getenv("LLM_TYPE", "oneapi")
ONEAPI_API_BASE = os.getenv("ONEAPI_API_BASE", "http://localhost:3000/v1").strip()
ONEAPI_API_KEY = os.getenv("ONEAPI_API_KEY", "")
ONEAPI_MODEL_NAME = os.getenv("ONEAPI_MODEL_NAME", "qwen-turbo")

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1").strip()
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "llama3.1:latest")

EMBEDDING_API_BASE = os.getenv("EMBEDDING_API_BASE", ONEAPI_API_BASE).strip()
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", ONEAPI_API_KEY)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v3")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "8"))

CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "knowledge_assistant")
LONG_MEMORY_COLLECTION_NAME = os.getenv("LONG_MEMORY_COLLECTION_NAME", "knowledge_assistant_memory")
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "3"))
KEYWORD_TOP_K = int(os.getenv("KEYWORD_TOP_K", "5"))
HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.65"))
HYBRID_KEYWORD_WEIGHT = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.35"))
RERANK_KEYWORD_WEIGHT = float(os.getenv("RERANK_KEYWORD_WEIGHT", "0.2"))
RERANK_SOURCE_WEIGHT = float(os.getenv("RERANK_SOURCE_WEIGHT", "0.1"))
CHUNK_SIZE_TOKENS = int(os.getenv("CHUNK_SIZE_TOKENS", "512"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "80"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"
QUERY_CACHE_TTL_SECONDS = int(os.getenv("QUERY_CACHE_TTL_SECONDS", "600"))
SESSION_CACHE_TTL_SECONDS = int(os.getenv("SESSION_CACHE_TTL_SECONDS", "86400"))
REVIEW_TASK_TTL_SECONDS = int(os.getenv("REVIEW_TASK_TTL_SECONDS", "86400"))
RERANK_CACHE_TTL_SECONDS = int(os.getenv("RERANK_CACHE_TTL_SECONDS", "600"))
QUERY_EXPANSION_CACHE_TTL_SECONDS = int(os.getenv("QUERY_EXPANSION_CACHE_TTL_SECONDS", "86400"))
REVIEW_MIN_EVIDENCE_COUNT = int(os.getenv("REVIEW_MIN_EVIDENCE_COUNT", "2"))
REVIEW_MIN_TOP_SCORE = float(os.getenv("REVIEW_MIN_TOP_SCORE", "0.55"))
REVIEW_MAX_SOURCE_COUNT = int(os.getenv("REVIEW_MAX_SOURCE_COUNT", "2"))
REVIEW_MIN_DOMINANT_SOURCE_RATIO = float(os.getenv("REVIEW_MIN_DOMINANT_SOURCE_RATIO", "0.6"))

FILE_SANDBOX_ROOT = Path(os.getenv("FILE_SANDBOX_ROOT", str(INPUT_DIR))).resolve()
