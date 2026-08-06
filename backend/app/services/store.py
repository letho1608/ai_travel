from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4


@dataclass
class StoredPlan:
    token: str
    session_id: str
    plan: dict
    request: dict
    version: int
    expires_at: datetime | None
    user_id: str | None = None


class MemoryStore:
    def __init__(self) -> None:
        self.plans: dict[str, StoredPlan] = {}
        self.profile: dict[str, dict[str, int]] = {}
        self.events: list[dict] = []
        self.cost_usd = 0.0
        self.monthly_cost_usd = 0.0
        self.nonces: dict[tuple[str, str], str] = {}
        self.reminders_sent: set[str] = set()
        self.ai_calls: list[dict] = []
        self.versions: dict[str, list[dict]] = {}
        self.users: dict[str, dict] = {}
        self.comments: dict[str, list[dict]] = {}
        self.inventory_snapshots: dict[str, dict] = {}
        self.booking_requests: dict[str, dict] = {}
        self.feedback: dict[str, dict] = {}
        self.preferences: dict[str, dict] = {}
        self.notifications: dict[str, dict] = {}
        self.available = True
        self._lock = Lock()

    def ensure_budget(self, daily_limit: float) -> None:
        if not self.available or self.cost_usd >= daily_limit:
            raise RuntimeError("Bộ đếm chi phí không sẵn sàng hoặc đã đạt trần")

    def reserve_cost(self, amount: float, daily_limit: float, monthly_limit: float) -> None:
        with self._lock:
            if not self.available:
                raise RuntimeError("Bộ đếm chi phí không sẵn sàng")
            if self.cost_usd + amount > daily_limit or self.monthly_cost_usd + amount > monthly_limit:
                raise RuntimeError("Đã đạt trần chi phí AI")
            self.cost_usd += amount
            self.monthly_cost_usd += amount

    def record_ai_usage(
        self, provider: str, model: str, input_tokens: int, output_tokens: int,
        amount: float, daily_limit: float, monthly_limit: float,
    ) -> None:
        self.reserve_cost(amount, daily_limit, monthly_limit)
        self.ai_calls.append(
            {"provider": provider, "model": model, "input_tokens": input_tokens,
             "output_tokens": output_tokens, "cost_usd": amount,
             "success": True, "created_at": datetime.now(UTC).isoformat()}
        )

    def save(self, session_id: str, plan: dict, request: dict) -> StoredPlan:
        item = StoredPlan(str(uuid4()), session_id, plan, request, 1, datetime.now(UTC) + timedelta(days=30))
        with self._lock:
            self.plans[item.token] = item
            self.versions[item.token] = [
                {"phien_ban": 1, "du_lieu": plan, "yeu_cau": request, "ly_do": "Tạo mới"}
            ]
        return item

    def get(self, token: str) -> StoredPlan | None:
        item = self.plans.get(token)
        if item and item.expires_at and item.expires_at < datetime.now(UTC):
            return None
        return item

    def update(
        self, item: StoredPlan, expected_version: int, plan: dict,
        request: dict | None = None, reason: str | None = None,
    ) -> None:
        with self._lock:
            if item.version != expected_version:
                raise ValueError("VERSION_CONFLICT")
            item.plan, item.version = plan, item.version + 1
            if request is not None:
                item.request = request
            self.versions.setdefault(item.token, []).append(
                {"phien_ban": item.version, "du_lieu": plan,
                 "yeu_cau": item.request, "ly_do": reason}
            )

    def list_versions(self, token: str) -> list[dict]:
        return list(reversed(self.versions.get(token, [])))

    def get_version(self, token: str, version: int) -> dict | None:
        return next(
            (entry for entry in self.versions.get(token, [])
             if entry["phien_ban"] == version), None
        )

    def add_comment(
        self, token: str, session_id: str, user_id: str | None,
        display_name: str, content: str,
    ) -> dict:
        comment = {
            "id": str(uuid4()), "token": token, "ma_phien": session_id,
            "nguoi_dung_id": user_id, "ten_hien_thi": display_name,
            "noi_dung": content, "da_giai_quyet": False,
            "ngay_tao": datetime.now(UTC).isoformat(),
        }
        self.comments.setdefault(token, []).append(comment)
        return comment

    def list_comments(self, token: str) -> list[dict]:
        return list(self.comments.get(token, []))

    def resolve_comment(self, token: str, comment_id: str, resolved: bool) -> dict | None:
        comment = next(
            (item for item in self.comments.get(token, []) if item["id"] == comment_id),
            None,
        )
        if comment:
            comment["da_giai_quyet"] = resolved
        return comment

    def save_inventory_snapshot(
        self, session_id: str, kind: str, request: dict, result: dict,
    ) -> str:
        snapshot_id = str(uuid4())
        self.inventory_snapshots[snapshot_id] = {
            "id": snapshot_id, "ma_phien": session_id, "loai": kind,
            "yeu_cau": request, "ket_qua": result,
            "het_han_luc": result["provenance"]["expires_at"],
        }
        return snapshot_id

    def create_booking_request(
        self, snapshot_id: str, session_id: str, user_id: str | None,
        offer_id: str, note: str | None,
    ) -> dict:
        with self._lock:
            snapshot = self.inventory_snapshots.get(snapshot_id)
            if not snapshot or snapshot["ma_phien"] != session_id:
                raise ValueError("SNAPSHOT_NOT_FOUND")
            try:
                expires_at = datetime.fromisoformat(snapshot["het_han_luc"])
            except (TypeError, ValueError) as exc:
                raise ValueError("SNAPSHOT_NOT_FOUND") from exc
            if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
                raise ValueError("SNAPSHOT_NOT_FOUND")
            valid_ids = {offer["id"] for offer in snapshot["ket_qua"].get("offers", [])}
            if offer_id not in valid_ids:
                raise ValueError("OFFER_NOT_FOUND")
            existing = next(
                (item for item in self.booking_requests.values()
                 if item["snapshot_id"] == snapshot_id
                 and item["ma_phien"] == session_id
                 and item.get("nguoi_dung_id") == user_id
                 and item["offer_id"] == offer_id),
                None,
            )
            if existing:
                return existing.copy()
            request_id = str(uuid4())
            item = {"id": request_id, "snapshot_id": snapshot_id, "ma_phien": session_id,
                    "nguoi_dung_id": user_id, "offer_id": offer_id, "ghi_chu": note,
                    "trang_thai": "requested", "ngay_tao": datetime.now(UTC).isoformat()}
            self.booking_requests[request_id] = item
            return item.copy()

    def list_booking_requests(self, status: str | None = None) -> list[dict]:
        items = list(self.booking_requests.values())
        if status:
            items = [item for item in items if item["trang_thai"] == status]
        return sorted(items, key=lambda item: item["ngay_tao"])

    def admin_summary(self) -> dict:
        open_booking_statuses = {"requested", "reviewing", "needs_customer"}
        return {
            "plans": len(self.plans),
            "users": len(self.users),
            "events": len(self.events),
            "comments": sum(len(items) for items in self.comments.values()),
            "feedback": len(self.feedback),
            "inventory_snapshots": len(self.inventory_snapshots),
            "booking_requests": len(self.booking_requests),
            "open_booking_requests": sum(
                1 for item in self.booking_requests.values()
                if item["trang_thai"] in open_booking_statuses
            ),
            "notifications": len(self.notifications),
            "ai_calls": len(self.ai_calls),
            "daily_ai_cost_usd": round(self.cost_usd, 8),
            "monthly_ai_cost_usd": round(self.monthly_cost_usd, 8),
        }

    def recent_events(self, limit: int = 20) -> list[dict]:
        return list(reversed(self.events[-limit:]))

    def admin_events(self, query: str = "", limit: int = 50) -> list[dict]:
        normalized = query.casefold().strip()
        rows = []
        for event in reversed(self.events):
            haystack = " ".join(
                [
                    str(event.get("ma_phien", "")),
                    str(event.get("su_kien", "")),
                    str(event.get("du_lieu", "")),
                ]
            ).casefold()
            if normalized and normalized not in haystack:
                continue
            rows.append(event)
            if len(rows) >= limit:
                break
        return rows

    def admin_users(self, query: str = "", limit: int = 30) -> list[dict]:
        normalized = query.casefold().strip()
        rows = []
        for user in self.users.values():
            haystack = " ".join(
                [user.get("id", ""), user.get("email", ""), user.get("ten") or "", user.get("nha_cung_cap", "")]
            ).casefold()
            if normalized and normalized not in haystack:
                continue
            user_id = user["id"]
            rows.append({
                "id": user_id,
                "email": user["email"],
                "name": user.get("ten"),
                "provider": user.get("nha_cung_cap"),
                "plans": sum(1 for item in self.plans.values() if item.user_id == user_id),
                "comments": sum(
                    1 for comments in self.comments.values()
                    for comment in comments if comment.get("nguoi_dung_id") == user_id
                ),
                "booking_requests": sum(
                    1 for item in self.booking_requests.values()
                    if item.get("nguoi_dung_id") == user_id
                ),
                "feedback": sum(
                    1 for item in self.feedback.values()
                    if item.get("nguoi_dung_id") == user_id
                ),
                "notifications": sum(
                    1 for item in self.notifications.values()
                    if item.get("nguoi_dung_id") == user_id
                ),
            })
        rows.sort(key=lambda value: value["email"])
        return rows[:limit]

    def admin_ai_usage(self, limit: int = 30) -> list[dict]:
        return list(reversed(self.ai_calls[-limit:]))

    def update_booking_request(
        self, request_id: str, status: str, assignee: str,
        internal_note: str | None, provider_reference: str | None,
    ) -> dict:
        item = self.booking_requests.get(request_id)
        if not item:
            raise ValueError("BOOKING_REQUEST_NOT_FOUND")
        allowed = {
            "requested": {"reviewing", "cancelled"},
            "reviewing": {"needs_customer", "handed_off", "cancelled"},
            "needs_customer": {"reviewing", "cancelled"},
            "handed_off": set(), "cancelled": set(),
        }
        if status not in allowed[item["trang_thai"]]:
            raise ValueError("INVALID_BOOKING_TRANSITION")
        item.update({"trang_thai": status, "phu_trach": assignee,
                     "provider_reference": provider_reference,
                     "ngay_cap_nhat": datetime.now(UTC).isoformat()})
        item.setdefault("lich_su", []).append(
            {"trang_thai": status, "phu_trach": assignee,
             "ghi_chu_noi_bo": internal_note,
             "provider_reference": provider_reference,
             "ngay_tao": item["ngay_cap_nhat"]}
        )
        return item.copy()

    def save_feedback(
        self, token: str, session_id: str, user_id: str | None,
        score: int, content: str | None,
    ) -> dict:
        key = f"{token}:{user_id or session_id}"
        if key in self.feedback:
            raise ValueError("FEEDBACK_EXISTS")
        item = {"id": str(uuid4()), "token": token, "ma_phien": session_id,
                "nguoi_dung_id": user_id, "diem": score, "noi_dung": content,
                "ngay_tao": datetime.now(UTC).isoformat()}
        self.feedback[key] = item
        return item

    def get_user_by_id(self, user_id: str) -> dict | None:
        return self.users.get(user_id)

    def delete_user_data(self, user_id: str) -> None:
        if user_id not in self.users:
            raise ValueError("USER_NOT_FOUND")
        owned_tokens = {
            token for token, item in self.plans.items() if item.user_id == user_id
        }
        for token in owned_tokens:
            self.plans.pop(token, None)
            self.versions.pop(token, None)
            self.comments.pop(token, None)
        for token, comments in list(self.comments.items()):
            self.comments[token] = [
                comment for comment in comments if comment.get("nguoi_dung_id") != user_id
            ]
        self.feedback = {
            key: value for key, value in self.feedback.items()
            if value.get("nguoi_dung_id") != user_id and value.get("token") not in owned_tokens
        }
        self.booking_requests = {
            key: value for key, value in self.booking_requests.items()
            if value.get("nguoi_dung_id") != user_id
        }
        self.notifications = {
            key: value for key, value in self.notifications.items()
            if value.get("nguoi_dung_id") != user_id
            and value.get("ke_hoach_id") not in owned_tokens
        }
        self.preferences.pop(user_id, None)
        self.users.pop(user_id, None)

    def get_preferences(self, session_id: str, user_id: str | None) -> dict:
        key = user_id or session_id
        return self.preferences.get(
            key, {"ngon_ngu": "vi", "tien_te": "VND", "don_vi": "metric"}
        )

    def save_preferences(
        self, session_id: str, user_id: str | None, preferences: dict,
    ) -> dict:
        self.preferences[user_id or session_id] = preferences
        return preferences

    def log(self, session_id: str, event: str, data: dict | None = None) -> None:
        self.events.append(
            {
                "ma_phien": session_id,
                "su_kien": event,
                "du_lieu": data or {},
                "thoi_gian": datetime.now(UTC).isoformat(),
            }
        )

    def cleanup_expired(self) -> int:
        now = datetime.now(UTC)
        expired = [
            token
            for token, item in self.plans.items()
            if item.expires_at is not None and item.expires_at < now
        ]
        for token in expired:
            self.plans.pop(token, None)
            self.versions.pop(token, None)
            self.comments.pop(token, None)
            self.nonces = {
                key: value for key, value in self.nonces.items() if key[0] != token
            }
            self.notifications = {
                key: value for key, value in self.notifications.items()
                if value.get("ke_hoach_id") != token
            }
        return len(expired)

    def list_all(self) -> list[StoredPlan]:
        return list(self.plans.values())

    def list_for_owner(self, session_id: str | None, user_id: str | None) -> list[StoredPlan]:
        return [
            item for item in self.plans.values()
            if self.get(item.token) is not None
            and (item.session_id == session_id or (user_id and item.user_id == user_id))
        ]

    def claim_session(self, session_id: str, user_id: str) -> int:
        claimed = 0
        with self._lock:
            for item in self.plans.values():
                if item.session_id == session_id:
                    item.user_id, item.expires_at = user_id, None
                    claimed += 1
        return claimed

    def upsert_user_and_claim(
        self, provider: str, email: str, name: str | None, session_id: str,
        policy_version: str,
    ) -> dict:
        existing = next((user for user in self.users.values() if user["email"] == email), None)
        user = existing or {"id": str(uuid4()), "email": email, "ten": name,
                            "nha_cung_cap": provider}
        self.users[user["id"]] = user
        self.claim_session(session_id, user["id"])
        self.log(session_id, "dong_y_chinh_sach", {"phien_ban": policy_version})
        return user

    def penalize_tags(self, session_id: str, tags: tuple[str, ...]) -> None:
        profile = self.profile.setdefault(session_id, {})
        for tag in tags:
            profile[tag] = profile.get(tag, 0) - 1

    def get_nonce(self, plan_token: str, nonce: str) -> str | None:
        return self.nonces.get((plan_token, nonce))

    def set_nonce(self, plan_token: str, nonce: str, result_token: str) -> str:
        with self._lock:
            return self.nonces.setdefault((plan_token, nonce), result_token)

    def claim_due_reminders(self) -> list[StoredPlan]:
        now = datetime.now(UTC)
        deadline = now + timedelta(hours=24)
        claimed: list[StoredPlan] = []
        with self._lock:
            for item in self.plans.values():
                raw_date = item.request.get("ngay_di")
                if not raw_date or item.token in self.reminders_sent:
                    continue
                try:
                    departure = datetime.fromisoformat(raw_date).replace(tzinfo=UTC)
                except (TypeError, ValueError):
                    continue
                if now <= departure <= deadline:
                    self.reminders_sent.add(item.token)
                    claimed.append(item)
        return claimed

    def materialize_due_reminders(self) -> int:
        created = 0
        for item in self.claim_due_reminders():
            notification_id = str(uuid4())
            self.notifications[notification_id] = {
                "id": notification_id, "ke_hoach_id": item.token,
                "plan_token": item.token,
                "plan_title": item.plan["tieu_de"],
                "nguoi_dung_id": item.user_id, "ma_phien": item.session_id,
                "loai": "trip_24h", "noi_dung": f"Chuyến đi {item.plan['tieu_de']} sắp bắt đầu.",
                "da_doc": False, "ngay_tao": datetime.now(UTC).isoformat(),
            }
            created += 1
        return created

    def list_notifications(self, session_id: str, user_id: str | None) -> list[dict]:
        return sorted(
            [item.copy() for item in self.notifications.values()
             if (user_id and item["nguoi_dung_id"] == user_id)
             or (not user_id and item["ma_phien"] == session_id)],
            key=lambda item: item["ngay_tao"], reverse=True,
        )

    def mark_notification_read(
        self, notification_id: str, session_id: str, user_id: str | None,
    ) -> dict:
        item = self.notifications.get(notification_id)
        allowed = item and ((user_id and item["nguoi_dung_id"] == user_id)
                            or (not user_id and item["ma_phien"] == session_id))
        if not allowed:
            raise ValueError("NOTIFICATION_NOT_FOUND")
        item["da_doc"] = True
        return item.copy()


def create_store():
    import os

    durable_local = os.getenv("USE_DURABLE_LOCAL", "false").lower() == "true"
    if os.getenv("APP_ENV", "local") == "local" and not durable_local:
        return MemoryStore()
    from app.services.postgres_store import PostgresStore

    database_url = os.getenv("URL_CSDL_POSTGRES")
    if not database_url:
        raise RuntimeError("URL_CSDL_POSTGRES is required outside local mode")
    return PostgresStore(database_url)


store = create_store()
