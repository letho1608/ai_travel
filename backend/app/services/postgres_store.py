import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from app.services.store import StoredPlan


class PostgresStore:
    """Durable store. Every mutation is committed atomically in PostgreSQL."""

    available = True

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.reminders_sent: set[str] = set()
        with self._connect() as connection:
            connection.execute("SELECT 1")

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=3)

    @staticmethod
    def _record(row: dict | None) -> StoredPlan | None:
        if not row:
            return None
        return StoredPlan(
            token=str(row["ma_chia_se"]), session_id=row["ma_phien"], plan=row["du_lieu"],
            request=row["yeu_cau"], version=row["phien_ban"], expires_at=row["ngay_het_han"],
            user_id=str(row["nguoi_dung_id"]) if row["nguoi_dung_id"] else None,
        )

    def ensure_budget(self, daily_limit: float) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT tong_usd FROM chi_phi_ai_ngay WHERE ngay=%s",
                (datetime.now(UTC).date(),),
            ).fetchone()
            if row and float(row["tong_usd"]) >= daily_limit:
                raise RuntimeError("Đã đạt trần chi phí AI trong ngày")

    def reserve_cost(self, amount: float, daily_limit: float, monthly_limit: float) -> None:
        with self._connect() as connection, connection.transaction():
            month_total = connection.execute(
                "SELECT COALESCE(SUM(tong_usd),0) AS total FROM chi_phi_ai_ngay "
                "WHERE ngay >= date_trunc('month', CURRENT_DATE)::date"
            ).fetchone()["total"]
            if float(month_total) + amount > monthly_limit:
                raise RuntimeError("Đã đạt trần chi phí AI trong tháng")
            row = connection.execute(
                "INSERT INTO chi_phi_ai_ngay(ngay,tong_usd) VALUES(CURRENT_DATE,%s) "
                "ON CONFLICT(ngay) DO UPDATE SET tong_usd=chi_phi_ai_ngay.tong_usd+EXCLUDED.tong_usd, "
                "ngay_cap_nhat=now() WHERE chi_phi_ai_ngay.tong_usd+EXCLUDED.tong_usd <= %s "
                "RETURNING tong_usd",
                (amount, daily_limit),
            ).fetchone()
            if not row:
                raise RuntimeError("Đã đạt trần chi phí AI trong ngày")

    def record_ai_usage(
        self, provider: str, model: str, input_tokens: int, output_tokens: int,
        amount: float, daily_limit: float, monthly_limit: float,
    ) -> None:
        with self._connect() as connection, connection.transaction():
            month_total = connection.execute(
                "SELECT COALESCE(SUM(tong_usd),0) AS total FROM chi_phi_ai_ngay "
                "WHERE ngay >= date_trunc('month', CURRENT_DATE)::date"
            ).fetchone()["total"]
            if float(month_total) + amount > monthly_limit:
                raise RuntimeError("Đã đạt trần chi phí AI trong tháng")
            budget = connection.execute(
                "INSERT INTO chi_phi_ai_ngay(ngay,tong_usd,so_token_vao,so_token_ra) "
                "VALUES(CURRENT_DATE,%s,%s,%s) ON CONFLICT(ngay) DO UPDATE SET "
                "tong_usd=chi_phi_ai_ngay.tong_usd+EXCLUDED.tong_usd,"
                "so_token_vao=chi_phi_ai_ngay.so_token_vao+EXCLUDED.so_token_vao,"
                "so_token_ra=chi_phi_ai_ngay.so_token_ra+EXCLUDED.so_token_ra,"
                "ngay_cap_nhat=now() WHERE "
                "chi_phi_ai_ngay.tong_usd+EXCLUDED.tong_usd <= %s RETURNING ngay",
                (amount, input_tokens, output_tokens, daily_limit),
            ).fetchone()
            if not budget:
                raise RuntimeError("Đã đạt trần chi phí AI trong ngày")
            connection.execute(
                "INSERT INTO lan_goi_ai(nha_cung_cap,model,token_vao,token_ra,chi_phi_usd) "
                "VALUES(%s,%s,%s,%s,%s)",
                (provider, model, input_tokens, output_tokens, amount),
            )

    def save(self, session_id: str, plan: dict, request: dict) -> StoredPlan:
        token, expires = uuid4(), datetime.now(UTC) + timedelta(days=30)
        departure = request.get("ngay_di")
        with self._connect() as connection, connection.transaction():
            row = connection.execute(
                "INSERT INTO ke_hoach(ma_chia_se,ma_phien,du_lieu,yeu_cau,ngay_di,ngay_nhac,ngay_het_han) "
                "VALUES(%s,%s,%s::jsonb,%s::jsonb,%s,%s::date - interval '1 day',%s) RETURNING *",
                (token, session_id, json.dumps(plan, ensure_ascii=False),
                 json.dumps(request, ensure_ascii=False), departure, departure, expires),
            ).fetchone()
            connection.execute(
                "INSERT INTO phien_ban_ke_hoach(ke_hoach_id,phien_ban,du_lieu,yeu_cau,ly_do) "
                "VALUES(%s,1,%s::jsonb,%s::jsonb,'Tạo mới')",
                (row["id"], json.dumps(plan, ensure_ascii=False),
                 json.dumps(request, ensure_ascii=False)),
            )
        return self._record(row)

    def get(self, token: str) -> StoredPlan | None:
        try:
            parsed = UUID(token)
        except ValueError:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ke_hoach WHERE ma_chia_se=%s AND "
                "(ngay_het_han IS NULL OR ngay_het_han > now())", (parsed,)
            ).fetchone()
        return self._record(row)

    def update(
        self, item: StoredPlan, expected_version: int, plan: dict,
        request: dict | None = None, reason: str | None = None,
    ) -> None:
        encoded_request = json.dumps(request, ensure_ascii=False) if request else None
        with self._connect() as connection, connection.transaction():
            row = connection.execute(
                "UPDATE ke_hoach SET du_lieu=%s::jsonb, "
                "yeu_cau=COALESCE(%s::jsonb,yeu_cau), phien_ban=phien_ban+1 "
                "WHERE ma_chia_se=%s AND phien_ban=%s RETURNING phien_ban",
                (json.dumps(plan, ensure_ascii=False), encoded_request,
                 UUID(item.token), expected_version),
            ).fetchone()
            if not row:
                raise ValueError("VERSION_CONFLICT")
            connection.execute(
                "INSERT INTO phien_ban_ke_hoach(ke_hoach_id,phien_ban,du_lieu,yeu_cau,ly_do) "
                "SELECT id,%s,%s::jsonb,yeu_cau,%s FROM ke_hoach WHERE ma_chia_se=%s",
                (row["phien_ban"], json.dumps(plan, ensure_ascii=False), reason,
                 UUID(item.token)),
            )
        item.plan, item.version = plan, row["phien_ban"]
        if request is not None:
            item.request = request

    def list_versions(self, token: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT v.phien_ban,v.du_lieu,v.yeu_cau,v.ly_do,v.ngay_tao "
                "FROM phien_ban_ke_hoach v JOIN ke_hoach k ON k.id=v.ke_hoach_id "
                "WHERE k.ma_chia_se=%s ORDER BY v.phien_ban DESC", (UUID(token),)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_version(self, token: str, version: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT v.phien_ban,v.du_lieu,v.yeu_cau,v.ly_do,v.ngay_tao "
                "FROM phien_ban_ke_hoach v JOIN ke_hoach k ON k.id=v.ke_hoach_id "
                "WHERE k.ma_chia_se=%s AND v.phien_ban=%s", (UUID(token), version)
            ).fetchone()
        return dict(row) if row else None

    def add_comment(
        self, token: str, session_id: str, user_id: str | None,
        display_name: str, content: str,
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "INSERT INTO binh_luan(ke_hoach_id,nguoi_dung_id,ma_phien,ten_hien_thi,noi_dung) "
                "SELECT id,%s,%s,%s,%s FROM ke_hoach WHERE ma_chia_se=%s RETURNING *",
                (UUID(user_id) if user_id else None, session_id, display_name, content,
                 UUID(token)),
            ).fetchone()
        if not row:
            raise ValueError("PLAN_NOT_FOUND")
        return {key: (str(value) if key in {"id", "nguoi_dung_id"} and value else value)
                for key, value in row.items() if key != "ke_hoach_id"}

    def list_comments(self, token: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT b.id,b.nguoi_dung_id,b.ma_phien,b.ten_hien_thi,b.noi_dung,"
                "b.da_giai_quyet,b.ngay_tao FROM binh_luan b JOIN ke_hoach k "
                "ON k.id=b.ke_hoach_id WHERE k.ma_chia_se=%s ORDER BY b.ngay_tao",
                (UUID(token),),
            ).fetchall()
        return [{key: (str(value) if key in {"id", "nguoi_dung_id"} and value else value)
                 for key, value in row.items()} for row in rows]

    def resolve_comment(self, token: str, comment_id: str, resolved: bool) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "UPDATE binh_luan b SET da_giai_quyet=%s FROM ke_hoach k "
                "WHERE b.ke_hoach_id=k.id AND k.ma_chia_se=%s AND b.id=%s RETURNING b.*",
                (resolved, UUID(token), UUID(comment_id)),
            ).fetchone()
        if not row:
            return None
        return {key: (str(value) if key in {"id", "nguoi_dung_id"} and value else value)
                for key, value in row.items() if key != "ke_hoach_id"}

    def save_inventory_snapshot(
        self, session_id: str, kind: str, request: dict, result: dict,
    ) -> str:
        provenance = result["provenance"]
        with self._connect() as connection:
            row = connection.execute(
                "INSERT INTO inventory_snapshot(ma_phien,loai,yeu_cau,ket_qua,nha_cung_cap,lay_luc,het_han_luc) "
                "VALUES(%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING id",
                (session_id, kind, json.dumps(request, ensure_ascii=False),
                 json.dumps(result, ensure_ascii=False), provenance["provider"],
                 provenance["fetched_at"], provenance["expires_at"]),
            ).fetchone()
        return str(row["id"])

    def create_booking_request(
        self, snapshot_id: str, session_id: str, user_id: str | None,
        offer_id: str, note: str | None,
    ) -> dict:
        identity = f"{snapshot_id}:{session_id}:{user_id or 'anonymous'}:{offer_id}"
        with self._connect() as connection, connection.transaction():
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (identity,),
            )
            snapshot = connection.execute(
                "SELECT ket_qua FROM inventory_snapshot WHERE id=%s AND ma_phien=%s "
                "AND het_han_luc>now()", (UUID(snapshot_id), session_id),
            ).fetchone()
            if not snapshot:
                raise ValueError("SNAPSHOT_NOT_FOUND")
            valid_ids = {offer["id"] for offer in snapshot["ket_qua"].get("offers", [])}
            if offer_id not in valid_ids:
                raise ValueError("OFFER_NOT_FOUND")
            existing = connection.execute(
                "SELECT * FROM yeu_cau_ho_tro_dat WHERE snapshot_id=%s "
                "AND ma_phien=%s AND nguoi_dung_id IS NOT DISTINCT FROM %s AND offer_id=%s",
                (UUID(snapshot_id), session_id, UUID(user_id) if user_id else None, offer_id),
            ).fetchone()
            if existing:
                row = existing
            else:
                row = connection.execute(
                    "INSERT INTO yeu_cau_ho_tro_dat(snapshot_id,ma_phien,nguoi_dung_id,offer_id,ghi_chu) "
                    "VALUES(%s,%s,%s,%s,%s) RETURNING *",
                    (UUID(snapshot_id), session_id, UUID(user_id) if user_id else None,
                     offer_id, note),
                ).fetchone()
        return {key: (str(value) if key in {"id", "snapshot_id", "nguoi_dung_id"} and value else value)
                for key, value in row.items()}

    def list_booking_requests(self, status: str | None = None) -> list[dict]:
        query = (
            "SELECT y.*, i.loai, i.yeu_cau, i.ket_qua, i.nha_cung_cap, i.het_han_luc "
            "FROM yeu_cau_ho_tro_dat y JOIN inventory_snapshot i ON i.id=y.snapshot_id "
        )
        params: tuple = ()
        if status:
            query += "WHERE y.trang_thai=%s "
            params = (status,)
        query += "ORDER BY y.ngay_tao ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {key: str(value) if isinstance(value, UUID) else value for key, value in row.items()}
            for row in rows
        ]

    def admin_summary(self) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                  (SELECT count(*) FROM ke_hoach) AS plans,
                  (SELECT count(*) FROM nguoi_dung) AS users,
                  (SELECT count(*) FROM nhat_ky) AS events,
                  (SELECT count(*) FROM binh_luan) AS comments,
                  (SELECT count(*) FROM phan_hoi_chuyen_di) AS feedback,
                  (SELECT count(*) FROM inventory_snapshot) AS inventory_snapshots,
                  (SELECT count(*) FROM yeu_cau_ho_tro_dat) AS booking_requests,
                  (SELECT count(*) FROM yeu_cau_ho_tro_dat
                   WHERE trang_thai IN ('requested','reviewing','needs_customer'))
                    AS open_booking_requests,
                  (SELECT count(*) FROM thong_bao) AS notifications,
                  (SELECT count(*) FROM lan_goi_ai) AS ai_calls,
                  (SELECT COALESCE(tong_usd,0) FROM chi_phi_ai_ngay
                   WHERE ngay=CURRENT_DATE) AS daily_ai_cost_usd,
                  (SELECT COALESCE(sum(tong_usd),0) FROM chi_phi_ai_ngay
                   WHERE ngay >= date_trunc('month', CURRENT_DATE)::date)
                    AS monthly_ai_cost_usd
                """
            ).fetchone()
        return {key: float(value) if key.endswith("_usd") else int(value)
                for key, value in row.items()}

    def recent_events(self, limit: int = 20) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT ma_phien,su_kien,du_lieu,thoi_gian FROM nhat_ky "
                "ORDER BY thoi_gian DESC LIMIT %s", (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def admin_events(self, query: str = "", limit: int = 50) -> list[dict]:
        normalized = f"%{query.casefold().strip()}%"
        where = ""
        params: tuple = ()
        if query.casefold().strip():
            where = (
                "WHERE lower(ma_phien) LIKE %s OR lower(su_kien) LIKE %s "
                "OR lower(du_lieu::text) LIKE %s "
            )
            params = (normalized, normalized, normalized)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT ma_phien,su_kien,du_lieu,thoi_gian FROM nhat_ky "
                f"{where}ORDER BY thoi_gian DESC LIMIT %s",
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def admin_users(self, query: str = "", limit: int = 30) -> list[dict]:
        normalized = f"%{query.casefold().strip()}%"
        where = ""
        params: tuple = ()
        if query.casefold().strip():
            where = (
                "WHERE lower(u.email) LIKE %s OR lower(COALESCE(u.ten,'')) LIKE %s "
                "OR lower(u.nha_cung_cap) LIKE %s OR u.id::text LIKE %s "
            )
            params = (normalized, normalized, normalized, normalized)
        sql = (
            "SELECT u.id,u.email,u.ten AS name,u.nha_cung_cap AS provider,"
            "COUNT(DISTINCT k.id) AS plans,"
            "COUNT(DISTINCT b.id) AS comments,"
            "COUNT(DISTINCT y.id) AS booking_requests,"
            "COUNT(DISTINCT f.id) AS feedback,"
            "COUNT(DISTINCT t.id) AS notifications "
            "FROM nguoi_dung u "
            "LEFT JOIN ke_hoach k ON k.nguoi_dung_id=u.id "
            "LEFT JOIN binh_luan b ON b.nguoi_dung_id=u.id "
            "LEFT JOIN yeu_cau_ho_tro_dat y ON y.nguoi_dung_id=u.id "
            "LEFT JOIN phan_hoi_chuyen_di f ON f.nguoi_dung_id=u.id "
            "LEFT JOIN thong_bao t ON t.nguoi_dung_id=u.id "
            f"{where}"
            "GROUP BY u.id,u.email,u.ten,u.nha_cung_cap "
            "ORDER BY u.email LIMIT %s"
        )
        with self._connect() as connection:
            rows = connection.execute(sql, (*params, limit)).fetchall()
        return [
            {key: str(value) if isinstance(value, UUID) else int(value) if key in {"plans", "comments", "booking_requests", "feedback", "notifications"} else value
             for key, value in row.items()}
            for row in rows
        ]

    def admin_ai_usage(self, limit: int = 30) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id,nha_cung_cap AS provider,model,token_vao AS input_tokens,"
                "token_ra AS output_tokens,chi_phi_usd AS cost_usd,thanh_cong AS success,"
                "thoi_gian AS created_at FROM lan_goi_ai ORDER BY thoi_gian DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return [
            {key: str(value) if isinstance(value, UUID) else float(value) if key == "cost_usd" else value
             for key, value in row.items()}
            for row in rows
        ]

    def update_booking_request(
        self, request_id: str, status: str, assignee: str,
        internal_note: str | None, provider_reference: str | None,
    ) -> dict:
        allowed = {
            "requested": {"reviewing", "cancelled"},
            "reviewing": {"needs_customer", "handed_off", "cancelled"},
            "needs_customer": {"reviewing", "cancelled"},
            "handed_off": set(), "cancelled": set(),
        }
        with self._connect() as connection:
            current = connection.execute(
                "SELECT trang_thai FROM yeu_cau_ho_tro_dat WHERE id=%s FOR UPDATE",
                (UUID(request_id),),
            ).fetchone()
            if not current:
                raise ValueError("BOOKING_REQUEST_NOT_FOUND")
            if status not in allowed[current["trang_thai"]]:
                raise ValueError("INVALID_BOOKING_TRANSITION")
            row = connection.execute(
                "UPDATE yeu_cau_ho_tro_dat SET trang_thai=%s,phu_trach=%s,"
                "provider_reference=%s,ngay_cap_nhat=now() WHERE id=%s RETURNING *",
                (status, assignee, provider_reference, UUID(request_id)),
            ).fetchone()
            connection.execute(
                "INSERT INTO lich_su_ho_tro_dat"
                "(yeu_cau_id,trang_thai,phu_trach,ghi_chu_noi_bo,provider_reference) "
                "VALUES(%s,%s,%s,%s,%s)",
                (UUID(request_id), status, assignee, internal_note, provider_reference),
            )
        return {key: str(value) if isinstance(value, UUID) else value for key, value in row.items()}

    def save_feedback(
        self, token: str, session_id: str, user_id: str | None,
        score: int, content: str | None,
    ) -> dict:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "INSERT INTO phan_hoi_chuyen_di(ke_hoach_id,nguoi_dung_id,ma_phien,diem,noi_dung) "
                    "SELECT id,%s,%s,%s,%s FROM ke_hoach WHERE ma_chia_se=%s RETURNING *",
                    (UUID(user_id) if user_id else None, session_id, score, content,
                     UUID(token)),
                ).fetchone()
        except psycopg.errors.UniqueViolation as exc:
            raise ValueError("FEEDBACK_EXISTS") from exc
        if not row:
            raise ValueError("PLAN_NOT_FOUND")
        return {key: (str(value) if key in {"id", "nguoi_dung_id"} and value else value)
                for key, value in row.items() if key != "ke_hoach_id"}

    def get_user_by_id(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id,email,ten,nha_cung_cap FROM nguoi_dung WHERE id=%s",
                (UUID(user_id),),
            ).fetchone()
        if not row:
            return None
        return {key: str(value) if isinstance(value, UUID) else value for key, value in row.items()}

    def delete_user_data(self, user_id: str) -> None:
        identifier = UUID(user_id)
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM nguoi_dung WHERE id=%s FOR UPDATE", (identifier,)
            ).fetchone()
            if not exists:
                raise ValueError("USER_NOT_FOUND")
            connection.execute(
                "DELETE FROM yeu_cau_ho_tro_dat WHERE nguoi_dung_id=%s", (identifier,)
            )
            connection.execute("DELETE FROM thong_bao WHERE nguoi_dung_id=%s", (identifier,))
            connection.execute("DELETE FROM binh_luan WHERE nguoi_dung_id=%s", (identifier,))
            connection.execute("DELETE FROM phan_hoi_chuyen_di WHERE nguoi_dung_id=%s", (identifier,))
            connection.execute("DELETE FROM ho_so_so_thich WHERE id_nguoi_dung=%s", (identifier,))
            connection.execute("DELETE FROM consent WHERE nguoi_dung_id=%s", (identifier,))
            connection.execute("DELETE FROM ke_hoach WHERE nguoi_dung_id=%s", (identifier,))
            connection.execute("DELETE FROM nguoi_dung WHERE id=%s", (identifier,))

    def get_preferences(self, session_id: str, user_id: str | None) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT ngon_ngu,tien_te,don_vi FROM ho_so_so_thich "
                "WHERE (id_nguoi_dung=%s OR (%s IS NULL AND ma_phien=%s)) "
                "ORDER BY id_nguoi_dung NULLS LAST LIMIT 1",
                (UUID(user_id) if user_id else None, user_id, session_id),
            ).fetchone()
        return dict(row) if row else {"ngon_ngu": "vi", "tien_te": "VND", "don_vi": "metric"}

    def save_preferences(
        self, session_id: str, user_id: str | None, preferences: dict,
    ) -> dict:
        with self._connect() as connection, connection.transaction():
            if user_id:
                cursor = connection.execute(
                    "UPDATE ho_so_so_thich SET ngon_ngu=%s,tien_te=%s,don_vi=%s,ngay_cap_nhat=now() "
                    "WHERE id_nguoi_dung=%s",
                    (preferences["ngon_ngu"], preferences["tien_te"], preferences["don_vi"],
                     UUID(user_id)),
                )
                if cursor.rowcount == 0:
                    connection.execute(
                        "INSERT INTO ho_so_so_thich(id_nguoi_dung,ngon_ngu,tien_te,don_vi) "
                        "VALUES(%s,%s,%s,%s)",
                        (UUID(user_id), preferences["ngon_ngu"], preferences["tien_te"],
                         preferences["don_vi"]),
                    )
            else:
                cursor = connection.execute(
                    "UPDATE ho_so_so_thich SET ngon_ngu=%s,tien_te=%s,don_vi=%s,ngay_cap_nhat=now() "
                    "WHERE ma_phien=%s AND id_nguoi_dung IS NULL",
                    (preferences["ngon_ngu"], preferences["tien_te"], preferences["don_vi"],
                     session_id),
                )
                if cursor.rowcount == 0:
                    connection.execute(
                        "INSERT INTO ho_so_so_thich(ma_phien,ngon_ngu,tien_te,don_vi) "
                        "VALUES(%s,%s,%s,%s)",
                        (session_id, preferences["ngon_ngu"], preferences["tien_te"],
                         preferences["don_vi"]),
                    )
        return preferences

    def list_all(self) -> list[StoredPlan]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM ke_hoach").fetchall()
        return [self._record(row) for row in rows]

    def list_for_owner(self, session_id: str | None, user_id: str | None) -> list[StoredPlan]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ke_hoach WHERE (ma_phien=%s OR nguoi_dung_id=%s) "
                "AND (ngay_het_han IS NULL OR ngay_het_han > now()) ORDER BY ngay_tao DESC",
                (session_id, UUID(user_id) if user_id else None),
            ).fetchall()
        return [self._record(row) for row in rows]

    def claim_session(self, session_id: str, user_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE ke_hoach SET nguoi_dung_id=%s,ngay_het_han=NULL WHERE ma_phien=%s",
                (UUID(user_id), session_id),
            )
        return cursor.rowcount

    def upsert_user_and_claim(
        self, provider: str, email: str, name: str | None, session_id: str,
        policy_version: str,
    ) -> dict:
        with self._connect() as connection, connection.transaction():
            user = connection.execute(
                "INSERT INTO nguoi_dung(nha_cung_cap,email,ten) VALUES(%s,%s,%s) "
                "ON CONFLICT(email) DO UPDATE SET ten=COALESCE(EXCLUDED.ten,nguoi_dung.ten) "
                "RETURNING id,email,ten,nha_cung_cap",
                (provider, email, name),
            ).fetchone()
            connection.execute(
                "INSERT INTO consent(nguoi_dung_id,ma_phien,phien_ban_chinh_sach) "
                "VALUES(%s,%s,%s)", (user["id"], session_id, policy_version),
            )
            connection.execute(
                "UPDATE ke_hoach SET nguoi_dung_id=%s,ngay_het_han=NULL WHERE ma_phien=%s",
                (user["id"], session_id),
            )
        return {"id": str(user["id"]), "email": user["email"], "ten": user["ten"],
                "nha_cung_cap": user["nha_cung_cap"]}

    def log(self, session_id: str, event: str, data: dict | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO nhat_ky(ma_phien,su_kien,du_lieu) VALUES(%s,%s,%s::jsonb)",
                (session_id, event, json.dumps(data or {}, ensure_ascii=False)),
            )

    def penalize_tags(self, session_id: str, tags: tuple[str, ...]) -> None:
        # Atomic JSONB merge will be expanded when tag preferences become weighted ranking input.
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO ho_so_so_thich(ma_phien,trong_so_tag) VALUES(%s,%s::jsonb) "
                "ON CONFLICT DO NOTHING", (session_id, json.dumps({tag: -1 for tag in tags})),
            )

    def get_nonce(self, plan_token: str, nonce: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result_token FROM idempotency_key WHERE plan_token=%s AND nonce=%s",
                (UUID(plan_token), nonce),
            ).fetchone()
        return str(row["result_token"]) if row else None

    def set_nonce(self, plan_token: str, nonce: str, result_token: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "INSERT INTO idempotency_key(plan_token,nonce,result_token) VALUES(%s,%s,%s) "
                "ON CONFLICT(plan_token,nonce) DO UPDATE SET nonce=EXCLUDED.nonce RETURNING result_token",
                (UUID(plan_token), nonce, UUID(result_token)),
            ).fetchone()
        return str(row["result_token"])

    def cleanup_expired(self) -> int:
        with self._connect() as connection, connection.transaction():
            cursor = connection.execute(
                "DELETE FROM ke_hoach WHERE ngay_het_han IS NOT NULL AND ngay_het_han < now()"
            )
            deleted_plans = cursor.rowcount
            connection.execute(
                "DELETE FROM idempotency_key i WHERE NOT EXISTS "
                "(SELECT 1 FROM ke_hoach k WHERE k.ma_chia_se=i.plan_token)"
            )
            connection.execute(
                "DELETE FROM ho_so_so_thich h WHERE h.id_nguoi_dung IS NULL "
                "AND h.ngay_cap_nhat < now()-interval '30 days' AND NOT EXISTS "
                "(SELECT 1 FROM ke_hoach k WHERE k.ma_phien=h.ma_phien)"
            )
            connection.execute(
                "DELETE FROM inventory_snapshot i WHERE i.het_han_luc < now() AND NOT EXISTS "
                "(SELECT 1 FROM yeu_cau_ho_tro_dat y WHERE y.snapshot_id=i.id)"
            )
            connection.execute("DELETE FROM nhat_ky WHERE thoi_gian < now()-interval '30 days'")
        return deleted_plans

    def claim_due_reminders(self) -> list[StoredPlan]:
        """Atomically claim reminders so concurrent workers cannot send twice."""
        with self._connect() as connection, connection.transaction():
            rows = connection.execute(
                """
                WITH due AS (
                  SELECT id FROM ke_hoach
                  WHERE da_gui_nhac=false AND ngay_di IS NOT NULL
                    AND ngay_di::timestamptz >= now()
                    AND ngay_di::timestamptz <= now() + interval '24 hours'
                  FOR UPDATE SKIP LOCKED
                )
                UPDATE ke_hoach k SET da_gui_nhac=true
                FROM due WHERE k.id=due.id RETURNING k.*
                """
            ).fetchall()
        return [item for row in rows if (item := self._record(row)) is not None]

    def materialize_due_reminders(self) -> int:
        with self._connect() as connection, connection.transaction():
            rows = connection.execute(
                "SELECT id,nguoi_dung_id,ma_phien,du_lieu FROM ke_hoach "
                "WHERE da_gui_nhac=false AND ngay_di BETWEEN current_date AND current_date+1 "
                "FOR UPDATE SKIP LOCKED"
            ).fetchall()
            for row in rows:
                connection.execute(
                    "INSERT INTO thong_bao(ke_hoach_id,nguoi_dung_id,ma_phien,loai,noi_dung) "
                    "VALUES(%s,%s,%s,'trip_24h',%s) ON CONFLICT(ke_hoach_id,loai) DO NOTHING",
                    (row["id"], row["nguoi_dung_id"], row["ma_phien"],
                     f"Chuyến đi {row['du_lieu']['tieu_de']} sắp bắt đầu."),
                )
                connection.execute(
                    "UPDATE ke_hoach SET da_gui_nhac=true WHERE id=%s", (row["id"],)
                )
        return len(rows)

    def list_notifications(self, session_id: str, user_id: str | None) -> list[dict]:
        with self._connect() as connection:
            if user_id:
                rows = connection.execute(
                    "SELECT t.*,k.ma_chia_se AS plan_token,k.du_lieu->>'tieu_de' AS plan_title FROM thong_bao t "
                    "JOIN ke_hoach k ON k.id=t.ke_hoach_id WHERE t.nguoi_dung_id=%s "
                    "ORDER BY t.ngay_tao DESC",
                    (UUID(user_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT t.*,k.ma_chia_se AS plan_token,k.du_lieu->>'tieu_de' AS plan_title FROM thong_bao t "
                    "JOIN ke_hoach k ON k.id=t.ke_hoach_id WHERE t.nguoi_dung_id IS NULL "
                    "AND t.ma_phien=%s ORDER BY t.ngay_tao DESC", (session_id,),
                ).fetchall()
        return [{key: str(value) if isinstance(value, UUID) else value
                 for key, value in row.items()} for row in rows]

    def mark_notification_read(
        self, notification_id: str, session_id: str, user_id: str | None,
    ) -> dict:
        with self._connect() as connection:
            if user_id:
                row = connection.execute(
                    "UPDATE thong_bao SET da_doc=true WHERE id=%s AND nguoi_dung_id=%s RETURNING *",
                    (UUID(notification_id), UUID(user_id)),
                ).fetchone()
            else:
                row = connection.execute(
                    "UPDATE thong_bao SET da_doc=true WHERE id=%s AND nguoi_dung_id IS NULL "
                    "AND ma_phien=%s RETURNING *", (UUID(notification_id), session_id),
                ).fetchone()
        if not row:
            raise ValueError("NOTIFICATION_NOT_FOUND")
        return {key: str(value) if isinstance(value, UUID) else value for key, value in row.items()}
