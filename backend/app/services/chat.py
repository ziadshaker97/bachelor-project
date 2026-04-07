from ..db import add_chat_message, load_chat_history
from ..models import ChatResponse, EmployeeProfile
from .llm import build_llm_adapter
from .recommendation import RecommendationService
from .retrieval import RetrievalService


class ChatService:
    def __init__(self) -> None:
        self.retrieval = RetrievalService()
        self.recommender = RecommendationService()
        self.llm = build_llm_adapter()

    def reply(self, session_id: str, profile: EmployeeProfile, message: str) -> ChatResponse:
        history = load_chat_history(session_id=session_id, employee_id=profile.employee_id)
        sources = self.retrieval.retrieve(message, history=history)
        recommended_module_ids: list[str] = []
        lower_message = message.lower()
        if any(keyword in lower_message for keyword in ("learn", "training", "module", "practice", "policy")):
            recommended_module_ids = [
                item.module_id
                for item in self.recommender.recommend(profile, top_k=2)
            ]

        answer = self.llm.generate(profile=profile, message=message, history=history, sources=sources)
        add_chat_message(session_id, profile.employee_id, "user", message)
        add_chat_message(session_id, profile.employee_id, "assistant", answer)
        return ChatResponse(
            answer=answer,
            sources=sources,
            recommended_module_ids=recommended_module_ids or None,
        )
