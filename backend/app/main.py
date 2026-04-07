from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .models import (
    ChatRequest,
    ChatResponse,
    DocumentsResponse,
    EmployeeProfile,
    ProfileResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from .seed import load_documents, load_modules
from .services.chat import ChatService
from .services.profiles import ProfileService
from .services.recommendation import RecommendationService


app = FastAPI(title="Employee Onboarding Intelligence MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

profiles = ProfileService()
recommender = RecommendationService()
chat = ChatService()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/profiles", response_model=ProfileResponse)
def upsert_profile(profile: EmployeeProfile) -> ProfileResponse:
    created = profiles.upsert_profile(profile)
    return ProfileResponse(profile=profile, created=created)


@app.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    profile = profiles.get_profile(request.employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    recommendations, strategy = recommender.recommend_with_strategy(profile=profile, top_k=request.top_k)
    return RecommendationResponse(employee_id=request.employee_id, recommendations=recommendations, strategy=strategy)


@app.post("/chat", response_model=ChatResponse)
def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    profile = profiles.get_profile(request.employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return chat.reply(session_id=request.session_id, profile=profile, message=request.message)


@app.get("/documents", response_model=DocumentsResponse)
def list_documents() -> DocumentsResponse:
    return DocumentsResponse(documents=load_documents(), modules=load_modules())
