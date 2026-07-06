import json
from dataclasses import dataclass
from typing import List

from cache.redis_cache import redis_cache
from config import PROPRIETARY_DICTIONARY_PATH, QUERY_EXPANSION_CACHE_TTL_SECONDS


@dataclass
class DictionaryHit:
    canonical: str
    matched: str
    aliases: List[str]


class ProprietaryDictionary:
    def __init__(self, path=PROPRIETARY_DICTIONARY_PATH):
        self.path = path
        self.entries = self._load_entries()

    def _load_entries(self) -> List[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save_entries(self):
        self.path.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert_entry(self, canonical: str, aliases: List[str]):
        normalized_aliases = sorted({alias.strip() for alias in aliases if alias.strip()})
        for entry in self.entries:
            if entry.get("canonical", "").casefold() == canonical.casefold():
                merged_aliases = set(entry.get("aliases", [])) | set(normalized_aliases)
                entry["canonical"] = canonical
                entry["aliases"] = sorted(merged_aliases)
                self._save_entries()
                return

        self.entries.append(
            {
                "canonical": canonical,
                "aliases": normalized_aliases,
            }
        )
        self._save_entries()

    def expand_query(self, query: str) -> tuple[str, List[DictionaryHit]]:
        cache_key = f"query_expansion:{query.casefold()}"
        cached = redis_cache.get_json(cache_key)
        if cached:
            hits = [DictionaryHit(**item) for item in cached.get("hits", [])]
            return cached.get("expanded_query", query), hits

        normalized_query = query.casefold()
        expansions = [query]
        hits: List[DictionaryHit] = []

        for entry in self.entries:
            canonical = entry.get("canonical", "").strip()
            aliases = [alias.strip() for alias in entry.get("aliases", []) if alias.strip()]
            vocabulary = [canonical, *aliases]
            matched = next(
                (term for term in vocabulary if term and term.casefold() in normalized_query),
                None,
            )
            if not matched:
                continue

            hits.append(
                DictionaryHit(
                    canonical=canonical,
                    matched=matched,
                    aliases=aliases,
                )
            )
            for term in vocabulary:
                if term and term not in expansions:
                    expansions.append(term)

        expanded_query = " ".join(expansions)
        redis_cache.set_json(
            cache_key,
            {
                "expanded_query": expanded_query,
                "hits": [hit.__dict__ for hit in hits],
            },
            ttl_seconds=QUERY_EXPANSION_CACHE_TTL_SECONDS,
        )
        return expanded_query, hits


query_dictionary = ProprietaryDictionary()
