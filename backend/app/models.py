from typing import List, Optional

from pydantic import BaseModel, Field


class EmployeeProfile(BaseModel):
    employee_id: str
    role: str
    department: str
    experience_level: str
    known_skills: List[str] = Field(default_factory=list)
    learning_preferences: List[str] = Field(default_factory=list)
    access_level: str = "employee"
    cv_summary: str = ""
    career_goals: List[str] = Field(default_factory=list)
    months_in_training: int = 0


class TrainingModule(BaseModel):
    module_id: str
    title: str
    topic_tags: List[str]
    difficulty: str
    format: str
    prerequisites: List[str] = Field(default_factory=list)
    role_tags: List[str] = Field(default_factory=list)
    description: str
    syllabus: List[str] = Field(default_factory=list)


class CourseRecord(BaseModel):
    course_id: str
    title: str
    provider: str
    category: str
    level: str
    duration_hours: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    description: str
    url: str
    delivery_mode: str = "external"
    syllabus: List[str] = Field(default_factory=list)


class CourseProgressRecord(BaseModel):
    employee_id: str
    course_id: str
    status: str
    progress_percent: int = Field(ge=0, le=100)
    saved_for_later: bool = False


class CourseProgressUpdate(BaseModel):
    employee_id: str
    course_id: str
    status: str
    progress_percent: int = Field(default=0, ge=0, le=100)
    saved_for_later: bool = False


class ModuleProgressRecord(BaseModel):
    employee_id: str
    module_id: str
    status: str
    progress_percent: int = Field(ge=0, le=100)
    saved_for_later: bool = False


class ModuleProgressUpdate(BaseModel):
    employee_id: str
    module_id: str
    status: str
    progress_percent: int = Field(default=0, ge=0, le=100)
    saved_for_later: bool = False


class RoadmapMilestone(BaseModel):
    milestone_id: str
    title: str
    phase: str
    description: str
    recommended_course_ids: List[str] = Field(default_factory=list)
    recommended_module_ids: List[str] = Field(default_factory=list)
    status: str = "upcoming"
    progress_percent: int = Field(default=0, ge=0, le=100)
    evidence: List[str] = Field(default_factory=list)


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
    recommended_courses: Optional[List[CourseRecord]] = None


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
    courses: List[CourseRecord]


class ProgressResponse(BaseModel):
    employee_id: str
    progress: List[CourseProgressRecord]


class ModuleProgressResponse(BaseModel):
    employee_id: str
    progress: List[ModuleProgressRecord]


class RoadmapResponse(BaseModel):
    employee_id: str
    role: str
    milestones: List[RoadmapMilestone]


class AdminEmployeeSummary(BaseModel):
    employee_id: str
    role: str
    department: str
    completed_courses: int
    in_progress_courses: int
    saved_courses: int
    completion_rate: int


class AdminSummaryResponse(BaseModel):
    total_employees: int
    total_courses_started: int
    total_courses_completed: int
    average_completion_rate: int
    employee_summaries: List[AdminEmployeeSummary]


class CourseSearchResponse(BaseModel):
    query: str
    provider: str
    configured: bool
    courses: List[CourseRecord]


class RecommendationAction(BaseModel):
    title: str
    detail: str
    action_type: str


class EmployeeInsightResponse(BaseModel):
    employee_id: str
    progress_stage: str
    ai_message: str
    strengths: List[str]
    skill_gaps: List[str]
    next_steps: List[RecommendationAction]
    recommended_module_ids: List[str]
    recommended_courses: List[CourseRecord]
