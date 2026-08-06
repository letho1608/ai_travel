import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest

from app.services.postgres_store import PostgresStore
from app.services.rate_limit import RedisRateLimiter

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv(
    "URL_CSDL_POSTGRES",
    "postgresql://postgres:postgres@localhost:5432/minhdidauthe",
)
REDIS_URL = os.getenv("URL_CSDL_REDIS", "redis://localhost:6379/0")


@pytest.fixture
def real_services():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("set RUN_INTEGRATION=1 with docker-compose services running")
    return PostgresStore(DATABASE_URL), RedisRateLimiter(REDIS_URL)


def test_durable_plan_invariants_and_redis_limit(real_services):
    store, limiter = real_services
    session = f"integration-{uuid4()}"
    request = {
        "ngay_di": (datetime.now(UTC) + timedelta(hours=20)).date().isoformat()
    }
    item = store.save(session, {"tieu_de": "Kiá»ƒm thá»­ tháº­t", "ngay": []}, request)
    redis_key = f"integration:{uuid4()}"
    multi_ip_key = f"integration-many-ip:{uuid4()}"
    multi_session_key = f"integration-many-session:{uuid4()}"
    try:
        assert store.get(item.token).plan["tieu_de"] == "Kiá»ƒm thá»­ tháº­t"
        store.update(item, 1, {"tieu_de": "ÄÃ£ cáº­p nháº­t", "ngay": []})
        assert store.get(item.token).version == 2
        versions = store.list_versions(item.token)
        assert [entry["phien_ban"] for entry in versions] == [2, 1]
        assert store.get_version(item.token, 1)["du_lieu"]["tieu_de"] == "Kiá»ƒm thá»­ tháº­t"
        with pytest.raises(ValueError, match="VERSION_CONFLICT"):
            store.update(item, 1, {"tieu_de": "Sai phiÃªn báº£n", "ngay": []})

        assert len(store.list_for_owner(session, None)) == 1
        first = store.set_nonce(item.token, "nonce-12345678", item.token)
        second = store.set_nonce(item.token, "nonce-12345678", str(uuid4()))
        assert first == second == item.token
        assert [plan.token for plan in store.claim_due_reminders()] == [item.token]
        assert store.claim_due_reminders() == []
        store.reserve_cost(0.001, 10, 300)

        assert limiter.check(redis_key, 2, 60)
        assert limiter.check(redis_key, 2, 60)
        assert not limiter.check(redis_key, 2, 60)
        assert limiter.check_many([(multi_session_key, 1, 60)])
        assert not limiter.check_many([(multi_ip_key, 10, 60), (multi_session_key, 1, 60)])
        assert limiter.check(multi_ip_key, 10, 60)
    finally:
        limiter.client.delete(f"rate:{redis_key}")
        limiter.client.delete(f"rate:{multi_ip_key}")
        limiter.client.delete(f"rate:{multi_session_key}")
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM idempotency_key WHERE plan_token=%s", (item.token,)
            )
            connection.execute("DELETE FROM ke_hoach WHERE ma_phien=%s", (session,))


def test_durable_booking_support_state_machine(real_services):
    store, _ = real_services
    session = f"support-integration-{uuid4()}"
    with psycopg.connect(DATABASE_URL) as connection:
        snapshot_id = connection.execute(
            "INSERT INTO inventory_snapshot"
            "(ma_phien,loai,yeu_cau,ket_qua,nha_cung_cap,lay_luc,het_han_luc) "
            "VALUES(%s,'hotel','{}',%s,'Amadeus',now(),now()+interval '15 minutes') RETURNING id",
            (session, '{"offers":[{"id":"live-offer"}]}'),
        ).fetchone()[0]
    try:
        request = store.create_booking_request(
            str(snapshot_id), session, None, "live-offer", "Kiá»ƒm thá»­ persistence"
        )
        duplicate = store.create_booking_request(
            str(snapshot_id), session, None, "live-offer", "ignored duplicate"
        )
        assert duplicate["id"] == request["id"]
        store.update_booking_request(
            request["id"], "reviewing", "Integration Operator", "ÄÃ£ nháº­n", None
        )
        handed_off = store.update_booking_request(
            request["id"], "handed_off", "Integration Operator",
            "ÄÃ£ chuyá»ƒn provider", "provider-case-integration",
        )
        assert handed_off["trang_thai"] == "handed_off"
        queued = next(
            item for item in store.list_booking_requests("handed_off")
            if item["id"] == request["id"]
        )
        assert queued["provider_reference"] == "provider-case-integration"
        with psycopg.connect(DATABASE_URL) as connection:
            assert connection.execute(
                "SELECT count(*) FROM lich_su_ho_tro_dat WHERE yeu_cau_id=%s",
                (request["id"],),
            ).fetchone()[0] == 2
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "DELETE FROM yeu_cau_ho_tro_dat WHERE snapshot_id=%s", (snapshot_id,)
            )
            connection.execute("DELETE FROM inventory_snapshot WHERE id=%s", (snapshot_id,))


def test_account_erasure_is_atomic_and_removes_owned_plans(real_services):
    store, _ = real_services
    session = f"erase-integration-{uuid4()}"
    item = store.save(session, {"tieu_de": "Sáº½ xÃ³a", "ngay": []}, {})
    user = store.upsert_user_and_claim(
        "google", f"{session}@example.com", "Erase Test", session, "2026-08-05"
    )
    try:
        assert store.get(item.token).user_id == user["id"]
        store.delete_user_data(user["id"])
        assert store.get_user_by_id(user["id"]) is None
        assert store.get(item.token) is None
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM ke_hoach WHERE ma_phien=%s", (session,))
            connection.execute("DELETE FROM nguoi_dung WHERE email=%s", (f"{session}@example.com",))


def test_maintenance_removes_expired_anonymous_plan_and_orphans(real_services):
    store, _ = real_services
    session = f"expired-integration-{uuid4()}"
    item = store.save(session, {"tieu_de": "ÄÃ£ háº¿t háº¡n", "ngay": []}, {})
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "UPDATE ke_hoach SET ngay_het_han=now()-interval '1 second' WHERE ma_chia_se=%s",
            (item.token,),
        )
        connection.execute(
            "INSERT INTO idempotency_key(plan_token,nonce,result_token) VALUES(%s,%s,%s)",
            (item.token, "expired-nonce", item.token),
        )
    assert store.cleanup_expired() >= 1
    assert store.get(item.token) is None
    with psycopg.connect(DATABASE_URL) as connection:
        assert connection.execute(
            "SELECT count(*) FROM idempotency_key WHERE plan_token=%s", (item.token,)
        ).fetchone()[0] == 0


def test_reminder_notification_persists_and_is_owner_scoped(real_services):
    store, _ = real_services
    session = f"notification-integration-{uuid4()}"
    request = {"ngay_di": (datetime.now(UTC) + timedelta(days=1)).date().isoformat()}
    item = store.save(session, {"tieu_de": "Chuyáº¿n sáº¯p Ä‘i", "ngay": []}, request)
    try:
        assert store.materialize_due_reminders() >= 1
        notification = next(
            value for value in store.list_notifications(session, None)
            if value["plan_token"] == item.token
        )
        assert notification["da_doc"] is False
        assert notification["plan_title"] == "Chuyáº¿n sáº¯p Ä‘i"
        assert store.list_notifications("other-session", None) == []
        assert store.mark_notification_read(notification["id"], session, None)["da_doc"] is True
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM ke_hoach WHERE ma_phien=%s", (session,))


