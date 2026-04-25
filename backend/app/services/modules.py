from ..db import load_module_progress, save_module_progress
from ..models import ModuleProgressRecord, ModuleProgressUpdate


class ModuleProgressService:
    def list_progress(self, employee_id: str) -> list[ModuleProgressRecord]:
        return [
            ModuleProgressRecord(
                employee_id=item["employee_id"],
                module_id=item["module_id"],
                status=item["status"],
                progress_percent=int(item["progress_percent"]),
                saved_for_later=bool(item["saved_for_later"]),
            )
            for item in load_module_progress(employee_id)
        ]

    def update_progress(self, payload: ModuleProgressUpdate) -> ModuleProgressRecord:
        save_module_progress(
            employee_id=payload.employee_id,
            module_id=payload.module_id,
            status=payload.status,
            progress_percent=payload.progress_percent,
            saved_for_later=payload.saved_for_later,
        )
        return self.list_progress(payload.employee_id)[-1]
