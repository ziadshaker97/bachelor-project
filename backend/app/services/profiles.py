from ..db import load_profile, save_profile
from ..models import EmployeeProfile


class ProfileService:
    def upsert_profile(self, profile: EmployeeProfile) -> bool:
        return save_profile(profile)

    def get_profile(self, employee_id: str) -> EmployeeProfile | None:
        return load_profile(employee_id)

