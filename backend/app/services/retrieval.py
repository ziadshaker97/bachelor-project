import math
import re
from collections import Counter

from ..config import TOP_K_DOCS
from ..models import DocumentRecord, SourceSnippet
from ..seed import load_documents


TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
MIN_SIMILARITY = 0.12
MIN_SHARED_TOKENS = 2
FOLLOW_UP_TOKENS = {
    "it",
    "that",
    "this",
    "they",
    "them",
    "those",
    "these",
    "who",
    "when",
    "where",
    "why",
    "how",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "do",
    "for",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "the",
    "to",
    "what",
    "when",
    "where",
    "who",
    "why",
    "you",
    "your"
}


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in STOPWORDS
    ]


class RetrievalService:
    def __init__(self) -> None:
        self.documents = load_documents()
        self.chunks = self._build_chunks(self.documents)

    def _build_chunks(self, documents: list[DocumentRecord]) -> list[dict]:
        chunks: list[dict] = []
        for document in documents:
            sections = [section.strip() for section in document.content.split("\n\n") if section.strip()]
            for index, section in enumerate(sections):
                chunks.append(
                    {
                        "document_id": document.document_id,
                        "title": document.title,
                        "chunk_id": f"{document.document_id}:{index}",
                        "text": section,
                        "vector": Counter(tokenize(section)),
                    }
                )
        return chunks

    def _rewrite_query(self, query: str, history: list[dict[str, str]] | None = None) -> str:
        history = history or []
        query_tokens = tokenize(query)
        recent_user_messages = [
            item["message"].strip()
            for item in reversed(history)
            if item.get("speaker") == "user" and item.get("message", "").strip()
        ]
        if not recent_user_messages:
            return query

        is_follow_up = (
            len(query_tokens) <= 4
            or any(token in FOLLOW_UP_TOKENS for token in query_tokens)
        )
        if not is_follow_up:
            return query

        context_messages = recent_user_messages[:2]
        combined_context = " ".join(reversed(context_messages))
        combined = f"{combined_context} {query}".strip()
        return combined.strip()

    @staticmethod
    def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
        keys = set(left) | set(right)
        dot = sum(left[key] * right[key] for key in keys)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def retrieve(self, query: str, top_k: int = TOP_K_DOCS, history: list[dict[str, str]] | None = None) -> list[SourceSnippet]:
        rewritten_query = self._rewrite_query(query, history=history)
        query_vector = Counter(tokenize(rewritten_query))
        ranked = []
        for chunk in self.chunks:
            score = self._cosine_similarity(query_vector, chunk["vector"])
            shared_tokens = set(query_vector) & set(chunk["vector"])
            if score >= MIN_SIMILARITY and len(shared_tokens) >= MIN_SHARED_TOKENS:
                ranked.append((score, chunk))
        ranked.sort(key=lambda item: item[0], reverse=True)
        snippets: list[SourceSnippet] = []
        for _, chunk in ranked[:top_k]:
            snippet = chunk["text"].replace("#", "").strip()
            snippets.append(
                SourceSnippet(
                    document_id=chunk["document_id"],
                    title=chunk["title"],
                    snippet=snippet[:280],
                )
            )
        return snippets
