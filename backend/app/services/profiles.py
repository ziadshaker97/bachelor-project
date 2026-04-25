from ..db import load_profile, save_profile
from ..models import EmployeeProfile
from ..seed import load_seed_profiles


class ProfileService:
    def upsert_profile(self, profile: EmployeeProfile) -> bool:
        return save_profile(profile)

    def get_profile(self, employee_id: str) -> EmployeeProfile | None:
        return load_profile(employee_id)

    def seed_defaults(self) -> None:
        for profile in load_seed_profiles():
            existing = load_profile(profile.employee_id)
            if existing is None or (
                profile.employee_id.startswith("emp-demo-")
                and (
                    existing.cv_summary != profile.cv_summary
                    or existing.career_goals != profile.career_goals
                    or existing.months_in_training != profile.months_in_training
                )
            ):
                save_profile(profile)
