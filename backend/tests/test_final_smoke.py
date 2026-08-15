import json
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "final_smoke.py"
spec = importlib.util.spec_from_file_location("final_smoke", SCRIPT)
final_smoke = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(final_smoke)


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def _healthy_payload_for(path: str, *, release_pass: bool) -> dict:
    if path.endswith("/health"):
        return {"status": "ok"}
    if path.endswith("/api/admin/catalog/quality"):
        return {"place_count": 35_605, "distance_matrix": {"loaded": True}}
    if path.endswith("/api/admin/ai-quality"):
        return {"live_provider_ready": True, "mode": "groq", "deterministic_rate_percent": 100}
    if path.endswith("/api/admin/dashboard"):
        return {"summary": {}, "provider_diagnostics": {}}
    if path.endswith("/api/admin/release-readiness"):
        return {"release_gate": {"pass": release_pass, "blockers": [] if release_pass else ["missing data"]}}
    raise AssertionError(f"unexpected URL {path}")


def test_final_smoke_fails_when_release_gate_fails(monkeypatch):
    def fake_urlopen(request, timeout=10):
        return FakeResponse(_healthy_payload_for(request.full_url, release_pass=False))

    monkeypatch.setattr(final_smoke, "urlopen", fake_urlopen)
    monkeypatch.delenv("ALLOW_UNREADY_RELEASE_SMOKE", raising=False)

    assert final_smoke.main() == 1


def test_final_smoke_passes_when_release_gate_passes(monkeypatch):
    def fake_urlopen(request, timeout=10):
        return FakeResponse(_healthy_payload_for(request.full_url, release_pass=True))

    monkeypatch.setattr(final_smoke, "urlopen", fake_urlopen)

    assert final_smoke.main() == 0


def test_final_smoke_can_bypass_release_gate_only_when_explicit(monkeypatch):
    def fake_urlopen(request, timeout=10):
        return FakeResponse(_healthy_payload_for(request.full_url, release_pass=False))

    monkeypatch.setattr(final_smoke, "urlopen", fake_urlopen)
    monkeypatch.setenv("ALLOW_UNREADY_RELEASE_SMOKE", "true")

    assert final_smoke.main() == 0
