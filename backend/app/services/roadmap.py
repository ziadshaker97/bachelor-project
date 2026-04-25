from __future__ import annotations

from ..models import EmployeeProfile, RoadmapMilestone
from ..seed import load_courses, load_modules, load_roadmaps
from .modules import ModuleProgressService
from .progress import ProgressService


PHASE_MONTH_TARGETS = {
    "Week 1": 0,
    "Week 2": 0,
    "Week 3": 0,
    "Month 1": 1,
    "Month 3": 3,
    "Month 6": 6,
}


class RoadmapService:
    def __init__(self) -> None:
        self.roadmaps = {}
        self.progress = ProgressService()
        self.module_progress = ModuleProgressService()
        self.courses = {course.course_id: course for course in load_courses()}
        self.modules = {module.module_id: module for module in load_modules()}

    def _refresh_roadmaps(self) -> None:
        self.roadmaps = load_roadmaps()

    @staticmethod
    def _current_phase_target(profile: EmployeeProfile) -> int:
        reached = [target for target in PHASE_MONTH_TARGETS.values() if profile.months_in_training >= target]
        return max(reached, default=0)

    @staticmethod
    def _phase_order(phase: str) -> int:
        order = {
            "Week 1": 1,
            "Week 2": 2,
            "Week 3": 3,
            "Month 1": 4,
            "Month 3": 5,
            "Month 6": 6,
        }
        return order.get(phase, 0)

    def _milestone_progress(self, profile: EmployeeProfile, milestone: RoadmapMilestone) -> RoadmapMilestone:
        progress_rows = self.progress.list_progress(profile.employee_id)
        module_progress_rows = self.module_progress.list_progress(profile.employee_id)
        progress_by_course = {item.course_id: item for item in progress_rows}
        progress_by_module = {item.module_id: item for item in module_progress_rows}
        completed = 0
        in_progress = 0
        evidence: list[str] = []

        for course_id in milestone.recommended_course_ids:
            course = self.courses.get(course_id)
            progress_item = progress_by_course.get(course_id)
            if progress_item and progress_item.status == "completed":
                completed += 1
                if course:
                    evidence.append(f"Completed {course.title}")
            elif progress_item and progress_item.status == "in_progress":
                in_progress += 1
                if course:
                    evidence.append(f"In progress: {course.title} ({progress_item.progress_percent}%)")

        for module_id in milestone.recommended_module_ids:
            module = self.modules.get(module_id)
            progress_item = progress_by_module.get(module_id)
            if progress_item and (progress_item.status == "completed" or progress_item.progress_percent >= 100):
                completed += 1
                if module:
                    evidence.append(f"Completed module {module.title}")
            elif progress_item and progress_item.status == "in_progress":
                in_progress += 1
                if module:
                    evidence.append(f"In progress: module {module.title} ({progress_item.progress_percent}%)")

        total_items = len(milestone.recommended_course_ids) + len(milestone.recommended_module_ids)
        course_ratio = ((completed + (0.5 * in_progress)) / total_items) if total_items else 0.0
        phase_month_target = PHASE_MONTH_TARGETS.get(milestone.phase, 0)
        current_phase_target = self._current_phase_target(profile)
        month_ratio = 1.0 if profile.months_in_training >= phase_month_target else min(1.0, profile.months_in_training / max(1, phase_month_target))
        progress_percent = int(round(((course_ratio * 0.75) + (month_ratio * 0.25)) * 100))

        if total_items and completed == total_items and profile.months_in_training >= phase_month_target:
            status = "completed"
        elif completed or in_progress or progress_percent >= 45:
            status = "active"
        else:
            status = "upcoming"

        if phase_month_target < current_phase_target and profile.months_in_training >= phase_month_target:
            status = "completed"
            progress_percent = max(progress_percent, 100)
            evidence = ["Historical onboarding record indicates this phase was completed earlier in the training journey."]
        elif profile.months_in_training >= 6 and milestone.phase in {"Week 1", "Week 2", "Week 3", "Month 1"} and status == "upcoming":
            status = "completed"
            progress_percent = max(progress_percent, 100)
            evidence.append("Historical onboarding duration indicates this phase has been reached.")

        return RoadmapMilestone(
            milestone_id=milestone.milestone_id,
            title=milestone.title,
            phase=milestone.phase,
            description=milestone.description,
            recommended_course_ids=milestone.recommended_course_ids,
            recommended_module_ids=milestone.recommended_module_ids,
            status=status,
            progress_percent=min(100, progress_percent),
            evidence=evidence,
        )

    def get_for_profile(self, profile: EmployeeProfile) -> list[RoadmapMilestone]:
        self._refresh_roadmaps()
        roadmap = self.roadmaps.get(profile.role, [])
        resolved = [self._milestone_progress(profile, milestone) for milestone in roadmap]
        current_phase_target = self._current_phase_target(profile)
        current_phase_index = max(
            (
                self._phase_order(item.phase)
                for item in resolved
                if PHASE_MONTH_TARGETS.get(item.phase, 0) == current_phase_target
            ),
            default=0,
        )
        gated: list[RoadmapMilestone] = []
        for milestone in resolved:
            milestone_index = self._phase_order(milestone.phase)
            if milestone_index < current_phase_index:
                gated.append(
                    RoadmapMilestone(
                        milestone_id=milestone.milestone_id,
                        title=milestone.title,
                        phase=milestone.phase,
                        description=milestone.description,
                        recommended_course_ids=milestone.recommended_course_ids,
                        recommended_module_ids=milestone.recommended_module_ids,
                        status="completed",
                        progress_percent=100,
                        evidence=["Historical onboarding record indicates this phase was completed earlier in the training journey."],
                    )
                )
            elif milestone_index > current_phase_index:
                gated.append(
                    RoadmapMilestone(
                        milestone_id=milestone.milestone_id,
                        title=milestone.title,
                        phase=milestone.phase,
                        description=milestone.description,
                        recommended_course_ids=milestone.recommended_course_ids,
                        recommended_module_ids=milestone.recommended_module_ids,
                        status="upcoming",
                        progress_percent=0,
                        evidence=[],
                    )
                )
            else:
                gated.append(milestone)
        return gated
