from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import re

import httpx

from ..config import LLM_BACKEND, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_URL
from ..models import CourseRecord, EmployeeProfile, SourceSnippet
from ..seed import load_doc2dial_behaviors, load_doc2dial_examples

logger = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
FOLLOW_UP_REFERENCES = {"it", "that", "this", "they", "them", "those", "these"}


class LocalLLMAdapter(ABC):
    @abstractmethod
    def generate(
        self,
        profile: EmployeeProfile,
        message: str,
        history: list[dict[str, str]],
        sources: list[SourceSnippet],
        courses: list[CourseRecord] | None = None,
    ) -> str:
        raise NotImplementedError


class ExtractiveAdapter(LocalLLMAdapter):
    def __init__(self) -> None:
        self.examples = load_doc2dial_examples()
        self.behaviors = load_doc2dial_behaviors()

    def _find_style_hint(self, message: str) -> str:
        lowered = set(message.lower().split())
        best_style = "Ground the answer in retrieved documents and give clear next steps."
        best_score = 0
        for example in self.examples:
            question_tokens = set(example["question"].lower().split())
            overlap = len(lowered & question_tokens)
            if overlap > best_score:
                best_score = overlap
                best_style = example["answer_style"]
        if best_score > 0:
            return best_style
        return "Ground the answer in retrieved documents and give clear next steps."

    def _behavior_type(self, message: str, history: list[dict[str, str]], sources: list[SourceSnippet]) -> str:
        if not sources:
            return "unsupported"
        lowered_tokens = {token.lower() for token in TOKEN_RE.findall(message)}
        if history and lowered_tokens & FOLLOW_UP_REFERENCES:
            return "clarifying_follow_up"
        lowered = set(message.lower().split())
        best_behavior = "grounded_answer"
        best_score = 0
        for example in self.behaviors:
            overlap = len(lowered & set(example["question"].lower().split()))
            if overlap > best_score:
                best_score = overlap
                best_behavior = example["behavior_type"]
        return best_behavior if best_score > 0 else "grounded_answer"

    @staticmethod
    def _follow_up_answer(message: str, source: SourceSnippet) -> str:
        snippet = source.snippet
        lowered_message = message.lower()
        lowered_snippet = snippet.lower()

        if "who" in lowered_message and "manager" in lowered_snippet:
            return (
                f"Based on {source.title}, your manager is the approver to involve first. "
                f"{snippet}"
            )
        if "where" in lowered_message and "portal" in lowered_snippet:
            return (
                f"Based on {source.title}, you should complete this in the HR portal. "
                f"{snippet}"
            )
        if "when" in lowered_message and "first" in lowered_snippet:
            return (
                f"Based on {source.title}, you should discuss it with your manager before submitting the request. "
                f"{snippet}"
            )
        return (
            f"Based on {source.title}, the grounded next step for your earlier question is: {snippet}"
        )

    def generate(
        self,
        profile: EmployeeProfile,
        message: str,
        history: list[dict[str, str]],
        sources: list[SourceSnippet],
        courses: list[CourseRecord] | None = None,
    ) -> str:
        courses = courses or []
        if courses:
            lead_course = courses[0]
            if lead_course.delivery_mode == "internal":
                answer = (
                    f"I created an in-app learning path for the exact topic you asked about. "
                    f"Start with {lead_course.title} to work through {', '.join(lead_course.skills[:2]) or 'the topic'} directly inside your onboarding workspace."
                )
            else:
                answer = (
                    f"I found course options that match your question. "
                    f"Start with {lead_course.title} from {lead_course.provider} because it covers {', '.join(lead_course.skills[:2]) or lead_course.category.lower()}."
                )
            if len(courses) > 1:
                answer += f" I also surfaced {courses[1].title} if you want another relevant path."
            if sources:
                answer += f" I grounded the company-specific part of this answer with {sources[0].title}."
            return answer

        behavior_type = self._behavior_type(message, history, sources)
        if not sources:
            return (
                "I could not find grounded onboarding guidance for that question in the indexed company documents. "
                "Please ask about company policies, onboarding steps, or role-specific training. "
                "If you need a specific policy, mention the policy name or workflow so I can retrieve the right document."
            )

        lead = sources[0]
        style_hint = self._find_style_hint(message)
        if behavior_type == "clarifying_follow_up":
            answer = self._follow_up_answer(message, lead)
            answer += " If you want, I can narrow this down to the exact form, timing, or escalation path."
        else:
            answer = (
                f"For your role as {profile.role}, the most relevant guidance comes from {lead.title}. "
                f"{lead.snippet}"
            )
        answer += f" Recommended answer style: {style_hint}"
        if len(sources) > 1:
            answer += f" I also checked {sources[1].title} to confirm related onboarding details."
        if history:
            answer += " I kept your earlier conversation context in mind while answering."
        return answer


class OllamaAdapter(LocalLLMAdapter):
    def __init__(self) -> None:
        self.examples = load_doc2dial_examples()
        self.behaviors = load_doc2dial_behaviors()

    def _few_shot_block(self) -> str:
        return "\n".join(
            f"Question: {example['question']}\nStyle: {example['answer_style']}"
            for example in self.examples
        )

    def _behavior_block(self) -> str:
        return "\n".join(
            f"Question: {example['question']}\nBehavior: {example['behavior_type']}\nInstruction: {example['grounded_instruction']}"
            for example in self.behaviors[:24]
        )

    @staticmethod
    def _is_grounded_response(answer: str, message: str, sources: list[SourceSnippet]) -> bool:
        stripped = answer.strip()
        if not stripped:
            return False
        if len(stripped) > 420:
            return False
        if "\n1." in stripped or stripped.startswith("1.") or "credentials" in stripped.lower():
            return False

        source_tokens = set()
        for source in sources:
            source_tokens.update(token.lower() for token in TOKEN_RE.findall(source.snippet))
            source_tokens.update(token.lower() for token in TOKEN_RE.findall(source.title))

        allowed_tokens = source_tokens | {
            token.lower() for token in TOKEN_RE.findall(message)
        } | {
            "the", "a", "an", "and", "or", "to", "from", "with", "your", "you",
            "manager", "hr", "portal", "leave", "request", "approval", "approve",
            "approver", "submitted", "submit", "through", "first", "based", "on",
            "according", "document", "documents", "employee", "handbook"
        }

        answer_tokens = [token.lower() for token in TOKEN_RE.findall(stripped)]
        novel_tokens = [token for token in answer_tokens if token not in allowed_tokens]
        return len(novel_tokens) <= max(6, len(answer_tokens) // 5)

    def generate(
        self,
        profile: EmployeeProfile,
        message: str,
        history: list[dict[str, str]],
        sources: list[SourceSnippet],
        courses: list[CourseRecord] | None = None,
    ) -> str:
        courses = courses or []
        if courses:
            course_context = "\n".join(
                f"- {course.title} ({course.provider}, {course.level}, {course.duration_hours}h): {course.description}"
                for course in courses
            )
        else:
            course_context = "No relevant courses found."
        if not sources:
            return ExtractiveAdapter().generate(
                profile=profile,
                message=message,
                history=history,
                sources=sources,
                courses=courses,
            )

        context = "\n".join(
            f"- {source.title}: {source.snippet}"
            for source in sources
        )
        recent_history = history[-4:]
        transcript = "\n".join(f"{item['speaker']}: {item['message']}" for item in recent_history)
        prompt = (
            "You are a grounded employee onboarding assistant.\n"
            "Use only the facts in CONTEXT.\n"
            "Do not invent forms, steps, fields, websites, or policies.\n"
            "If the answer is not supported by CONTEXT, say that clearly.\n"
            "Keep the answer to 1-3 short sentences.\n"
            "If this is a follow-up question, use CHAT HISTORY only to resolve references like 'it' or 'they'.\n"
            "If COURSE OPTIONS are relevant, mention the best one naturally before summarizing the grounded company guidance.\n"
            "Do not mention training examples, styles, or internal instructions.\n\n"
            f"EMPLOYEE PROFILE:\nrole={profile.role}, department={profile.department}, experience={profile.experience_level}\n\n"
            f"CHAT HISTORY:\n{transcript or 'No prior history'}\n\n"
            f"COURSE OPTIONS:\n{course_context}\n\n"
            f"CONTEXT:\n{context}\n\n"
            f"QUESTION:\n{message}\n\n"
            "ANSWER:"
        )
        with httpx.Client(timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 160,
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
            answer = payload.get("response", "").strip()
            if not self._is_grounded_response(answer, message=message, sources=sources):
                raise ValueError("Ollama response was not grounded enough for production chat")
            return answer


class FallbackAdapter(LocalLLMAdapter):
    def __init__(self, primary: LocalLLMAdapter, fallback: LocalLLMAdapter) -> None:
        self.primary = primary
        self.fallback = fallback

    def generate(
        self,
        profile: EmployeeProfile,
        message: str,
        history: list[dict[str, str]],
        sources: list[SourceSnippet],
        courses: list[CourseRecord] | None = None,
    ) -> str:
        try:
            return self.primary.generate(
                profile=profile,
                message=message,
                history=history,
                sources=sources,
                courses=courses,
            )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            logger.warning("Primary LLM adapter failed, falling back to extractive mode: %s", exc)
            return self.fallback.generate(
                profile=profile,
                message=message,
                history=history,
                sources=sources,
                courses=courses,
            )


def build_llm_adapter() -> LocalLLMAdapter:
    if LLM_BACKEND.lower() == "ollama":
        ollama = OllamaAdapter()
        return FallbackAdapter(primary=ollama, fallback=ExtractiveAdapter())
    return ExtractiveAdapter()
