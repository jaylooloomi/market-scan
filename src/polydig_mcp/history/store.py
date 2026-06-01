"""Historical-theme retrieval for the Reviewer.

Primary: Chroma vector store (semantic). Fallback: a pure-Python token-overlap
retriever so the Reviewer's precedent lookup still works offline / without the
embedding model download. Same query() interface either way.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_THEMES_PATH = Path(__file__).with_name("themes.json")
_CJK_RUN = re.compile(r"[一-鿿]+")
_LATIN = re.compile(r"[A-Za-z0-9]{2,}")


def load_themes() -> list[dict[str, Any]]:
    data = json.loads(_THEMES_PATH.read_text(encoding="utf-8"))
    return data["themes"]


def theme_document(theme: dict[str, Any]) -> str:
    """Flatten a theme into a searchable document string."""
    parts = [theme["name"], theme.get("trigger_event", ""), theme.get("notes", "")]
    for tier in theme.get("causal_tree", {}).values():
        for m in tier:
            parts.append(f"{m.get('name','')} {m.get('role','')}")
    for h in theme.get("historical_analogue", []):
        parts.append(h.get("event", ""))
    return " ".join(p for p in parts if p)


def _tokens(text: str) -> set[str]:
    """Latin words + CJK character bigrams (standard cheap Chinese retrieval).

    Bigrams keep query/doc vocab aligned: '航運三雄' -> {航運, 運三, 三雄} so a
    query '航運' still matches. Single chars added for short runs.
    """
    out = {t.lower() for t in _LATIN.findall(text)}
    for run in _CJK_RUN.findall(text):
        if len(run) == 1:
            out.add(run)
        else:
            out.update(run[i : i + 2] for i in range(len(run) - 1))
    return out


@dataclass
class Match:
    theme: dict[str, Any]
    score: float  # higher = more similar (0..1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.theme["id"],
            "name": self.theme["name"],
            "trigger_type": self.theme["trigger_type"],
            "reviewer_verdict": self.theme["reviewer_verdict"],
            "similarity": round(self.score, 3),
            "causal_tree": self.theme["causal_tree"],
            "historical_analogue": self.theme.get("historical_analogue", []),
            "outcome": self.theme.get("outcome"),
        }


class ThemeStore:
    """Semantic retriever over the seed themes, with graceful fallback."""

    def __init__(self, persist_dir: str | None = None):
        self._themes = load_themes()
        self._docs = {t["id"]: theme_document(t) for t in self._themes}
        self._by_id = {t["id"]: t for t in self._themes}
        self._collection = None
        self._mode = "fallback"
        if persist_dir is not None:
            self._try_chroma(persist_dir)

    def _try_chroma(self, persist_dir: str) -> None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=persist_dir)
            col = client.get_or_create_collection("polydig_themes")
            if col.count() < len(self._themes):
                col.upsert(
                    ids=list(self._docs.keys()),
                    documents=list(self._docs.values()),
                )
            self._collection = col
            self._mode = "chroma"
        except Exception:
            # Embedding model unavailable / chromadb missing -> stay on fallback.
            self._collection = None
            self._mode = "fallback"

    @property
    def mode(self) -> str:
        return self._mode

    def query(self, text: str, n_results: int = 3) -> list[Match]:
        if self._collection is not None:
            try:
                res = self._collection.query(query_texts=[text], n_results=n_results)
                ids = res["ids"][0]
                dists = res.get("distances", [[0.0] * len(ids)])[0]
                out = []
                for tid, dist in zip(ids, dists):
                    out.append(Match(self._by_id[tid], score=max(0.0, 1.0 - dist)))
                return out
            except Exception:
                pass  # fall through to token overlap
        return self._fallback_query(text, n_results)

    def _fallback_query(self, text: str, n_results: int) -> list[Match]:
        q = _tokens(text)
        scored: list[Match] = []
        for tid, doc in self._docs.items():
            d = _tokens(doc)
            if not d:
                continue
            overlap = len(q & d)
            # asymmetric Jaccard-ish; capped at 1.0 to honour the 0..1 contract
            # (Match.score docstring + REVIEW_JSON_SCHEMA confidence maximum=1).
            score = min(1.0, overlap / (len(q | d) ** 0.5)) if q else 0.0
            scored.append(Match(self._by_id[tid], score=score))
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:n_results]
