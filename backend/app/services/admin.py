from ..db import load_all_course_progress, load_all_profiles
from ..models import AdminEmployeeSummary, AdminSummaryResponse


class AdminService:
    def summary(self) -> AdminSummaryResponse:
        profiles = load_all_profiles()
        progress_rows = load_all_course_progress()
        progress_by_employee: dict[str, list[dict[str, int | str]]] = {}
        for row in progress_rows:
            progress_by_employee.setdefault(str(row["employee_id"]), []).append(row)

        employee_summaries: list[AdminEmployeeSummary] = []
        total_started = 0
        total_completed = 0
        completion_rates: list[int] = []

        for profile in profiles:
            rows = progress_by_employee.get(profile.employee_id, [])
            completed = sum(1 for row in rows if row["status"] == "completed")
            in_progress = sum(1 for row in rows if row["status"] == "in_progress")
            saved = sum(1 for row in rows if bool(row["saved_for_later"]))
            total = len(rows)
            completion_rate = int(round((completed / total) * 100)) if total else 0
            total_started += in_progress + completed
            total_completed += completed
            completion_rates.append(completion_rate)
            employee_summaries.append(
                AdminEmployeeSummary(
                    employee_id=profile.employee_id,
                    role=profile.role,
                    department=profile.department,
                    completed_courses=completed,
                    in_progress_courses=in_progress,
                    saved_courses=saved,
                    completion_rate=completion_rate,
                )
            )

        average_completion_rate = int(round(sum(completion_rates) / len(completion_rates))) if completion_rates else 0
        return AdminSummaryResponse(
            total_employees=len(profiles),
            total_courses_started=total_started,
            total_courses_completed=total_completed,
            average_completion_rate=average_completion_rate,
            employee_summaries=employee_summaries,
        )
