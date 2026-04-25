from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .models import (
    AdminSummaryResponse,
    ChatRequest,
    ChatResponse,
    CourseSearchResponse,
    CourseProgressUpdate,
    DocumentsResponse,
    EmployeeInsightResponse,
    EmployeeProfile,
    ModuleProgressResponse,
    ModuleProgressUpdate,
    ProgressResponse,
    ProfileResponse,
    RecommendationRequest,
    RecommendationResponse,
    RoadmapResponse,
)
from .seed import load_courses, load_documents, load_modules
from .services.admin import AdminService
from .services.chat import ChatService
from .services.employee_intelligence import EmployeeIntelligenceService
from .services.modules import ModuleProgressService
from .services.progress import ProgressService
from .services.profiles import ProfileService
from .services.recommendation import RecommendationService
from .services.roadmap import RoadmapService


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
progress = ProgressService()
module_progress = ModuleProgressService()
roadmap = RoadmapService()
admin = AdminService()
intelligence = EmployeeIntelligenceService()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    profiles.seed_defaults()
    progress.seed_defaults()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/profiles", response_model=ProfileResponse)
def upsert_profile(profile: EmployeeProfile) -> ProfileResponse:
    created = profiles.upsert_profile(profile)
    return ProfileResponse(profile=profile, created=created)


@app.get("/profiles/{employee_id}", response_model=ProfileResponse)
def get_profile(employee_id: str) -> ProfileResponse:
    profile = profiles.get_profile(employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Employee ID not found")
    return ProfileResponse(profile=profile, created=False)


@app.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    profile = profiles.get_profile(request.employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    progress_rows = module_progress.list_progress(request.employee_id)
    completed_module_ids = {
        item.module_id for item in progress_rows if item.status == "completed" or item.progress_percent >= 100
    }
    recommendations, strategy = recommender.recommend_with_strategy(profile=profile, top_k=max(request.top_k * 3, 10))
    recommendations = [
        item for item in recommendations
        if item.module_id not in completed_module_ids
    ][:request.top_k]
    return RecommendationResponse(employee_id=request.employee_id, recommendations=recommendations, strategy=strategy)


@app.post("/chat", response_model=ChatResponse)
def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    profile = profiles.get_profile(request.employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return chat.reply(session_id=request.session_id, profile=profile, message=request.message)


@app.get("/progress/{employee_id}", response_model=ProgressResponse)
def get_progress(employee_id: str) -> ProgressResponse:
    profile = profiles.get_profile(employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProgressResponse(employee_id=employee_id, progress=progress.list_progress(employee_id))


@app.post("/progress", response_model=ProgressResponse)
def update_progress(payload: CourseProgressUpdate) -> ProgressResponse:
    profile = profiles.get_profile(payload.employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    progress.update_progress(payload)
    return ProgressResponse(employee_id=payload.employee_id, progress=progress.list_progress(payload.employee_id))


@app.get("/module-progress/{employee_id}", response_model=ModuleProgressResponse)
def get_module_progress(employee_id: str) -> ModuleProgressResponse:
    profile = profiles.get_profile(employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ModuleProgressResponse(employee_id=employee_id, progress=module_progress.list_progress(employee_id))


@app.post("/module-progress", response_model=ModuleProgressResponse)
def update_module_progress(payload: ModuleProgressUpdate) -> ModuleProgressResponse:
    profile = profiles.get_profile(payload.employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    module_progress.update_progress(payload)
    return ModuleProgressResponse(employee_id=payload.employee_id, progress=module_progress.list_progress(payload.employee_id))


@app.get("/roadmap/{employee_id}", response_model=RoadmapResponse)
def get_roadmap(employee_id: str) -> RoadmapResponse:
    profile = profiles.get_profile(employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return RoadmapResponse(employee_id=employee_id, role=profile.role, milestones=roadmap.get_for_profile(profile))


@app.get("/admin/summary", response_model=AdminSummaryResponse)
def get_admin_summary() -> AdminSummaryResponse:
    return admin.summary()


@app.get("/employee-intelligence/{employee_id}", response_model=EmployeeInsightResponse)
def get_employee_intelligence(employee_id: str) -> EmployeeInsightResponse:
    profile = profiles.get_profile(employee_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return intelligence.build(profile)


@app.get("/documents", response_model=DocumentsResponse)
def list_documents() -> DocumentsResponse:
    return DocumentsResponse(documents=load_documents(), modules=load_modules(), courses=load_courses())


@app.get("/courses/search", response_model=CourseSearchResponse)
def search_courses(query: str, top_k: int = 10) -> CourseSearchResponse:
    course_service = chat.courses
    courses = course_service.search_external(query=query, top_k=top_k)
    return CourseSearchResponse(
        query=query,
        provider=course_service.external_provider.provider_name,
        configured=course_service.external_provider.configured(),
        courses=courses,
    )
