from typing import List, Optional

from pydantic import BaseModel, Field


class EmployeeProfile(BaseModel):
    employee_id: str
    role: str
    department: str
    experience_level: str
    known_skills: List[str] = Field(default_factory=list)
    learning_preferences: List[str] = Field(default_factory=list)


class TrainingModule(BaseModel):
    module_id: str
    title: str
    topic_tags: List[str]
    difficulty: str
    format: str
    prerequisites: List[str] = Field(default_factory=list)
    role_tags: List[str] = Field(default_factory=list)
    description: str


class RecommendationResult(BaseModel):
    module_id: str
    score: float
    reason_codes: List[str]
    reason_text: str


class SourceSnippet(BaseModel):
    document_id: str
    title: str
    snippet: str


class ChatRequest(BaseModel):
    session_id: str
    employee_id: str
    message: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceSnippet]
    recommended_module_ids: Optional[List[str]] = None


class ProfileResponse(BaseModel):
    profile: EmployeeProfile
    created: bool


class RecommendationRequest(BaseModel):
    employee_id: str
    top_k: int = Field(default=5, ge=1, le=10)


class RecommendationResponse(BaseModel):
    employee_id: str
    recommendations: List[RecommendationResult]
    strategy: Optional[str] = None


class DocumentRecord(BaseModel):
    document_id: str
    title: str
    category: str
    content: str


class DocumentsResponse(BaseModel):
    documents: List[DocumentRecord]
    modules: List[TrainingModule]
