from typing import Protocol

from app.services.store import StoredPlan


class ReminderStore(Protocol):
    def claim_due_reminders(self) -> list[StoredPlan]: ...


def due_in_app_reminders(store: ReminderStore) -> list[dict]:
    """Claim and return due reminders exactly once across concurrent workers."""
    return [
        {
            "token": item.token,
            "message": f"Chuyến đi {item.plan['tieu_de']} bắt đầu trong vòng 24 giờ.",
        }
        for item in store.claim_due_reminders()
    ]
