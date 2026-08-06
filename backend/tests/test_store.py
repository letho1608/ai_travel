from datetime import UTC, datetime, timedelta

from app.services.store import MemoryStore


def test_cleanup_removes_only_expired_anonymous_plans():
    memory = MemoryStore()
    old = memory.save("old", {}, {})
    kept = memory.save("kept", {}, {})
    old.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    kept.expires_at = None
    memory.versions[old.token] = [{"phien_ban": 1}]
    memory.comments[old.token] = [{"id": "comment"}]
    memory.nonces[(old.token, "nonce-12345678")] = old.token
    assert memory.cleanup_expired() == 1
    assert memory.get(kept.token) is kept
    assert old.token not in memory.versions
    assert old.token not in memory.comments
    assert all(key[0] != old.token for key in memory.nonces)
