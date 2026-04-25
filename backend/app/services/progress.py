from ..db import load_course_progress, save_course_progress, seed_course_progress
from ..models import CourseProgressRecord, CourseProgressUpdate
from ..seed import load_historical_progress


class ProgressService:
    def seed_defaults(self) -> None:
        seed_course_progress(load_historical_progress())

    def list_progress(self, employee_id: str) -> list[CourseProgressRecord]:
        return [
            CourseProgressRecord(
                employee_id=item["employee_id"],
                course_id=item["course_id"],
                status=item["status"],
                progress_percent=int(item["progress_percent"]),
                saved_for_later=bool(item["saved_for_later"]),
            )
            for item in load_course_progress(employee_id)
        ]

    def update_progress(self, payload: CourseProgressUpdate) -> CourseProgressRecord:
        save_course_progress(
            employee_id=payload.employee_id,
            course_id=payload.course_id,
            status=payload.status,
            progress_percent=payload.progress_percent,
            saved_for_later=payload.saved_for_later,
        )
        return self.list_progress(payload.employee_id)[-1]
