from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "http://localhost:8000"
ADMIN_TOKEN = "local-support-dev"


def get_json(path: str, *, admin: bool = False) -> dict:
    headers = {"X-Admin-Token": ADMIN_TOKEN} if admin else {}
    request = Request(f"{API_URL}{path}", headers=headers)
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def check(name: str, passed: bool, detail: str) -> bool:
    status = "PASS" if passed else "FAIL"
    print(f"{status} {name}: {detail}")
    return passed


def main() -> int:
    failures = 0
    try:
        health = get_json("/health")
        failures += not check("health", health.get("status") == "ok", json.dumps(health, ensure_ascii=False))
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"FAIL health: {exc}")
        return 1

    try:
        quality = get_json("/api/admin/catalog/quality", admin=True)
        failures += not check(
            "catalog_quality",
            quality.get("place_count", 0) >= 500 and quality.get("distance_matrix", {}).get("loaded") is True,
            f"places={quality.get('place_count')} distance_loaded={quality.get('distance_matrix', {}).get('loaded')}",
        )
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"FAIL catalog_quality: {exc}")
        failures += 1

    try:
        ai_quality = get_json("/api/admin/ai-quality", admin=True)
        live_ready = ai_quality.get("live_provider_ready") is True
        mode = ai_quality.get("mode")
        detail = (
            f"mode={mode} live_provider_ready={live_ready} "
            f"deterministic_rate={ai_quality.get('deterministic_rate_percent')}"
        )
        failures += not check("ai_quality", live_ready and mode != "offline", detail)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"FAIL ai_quality: {exc}")
        failures += 1

    try:
        dashboard = get_json("/api/admin/dashboard", admin=True)
        failures += not check(
            "admin_dashboard",
            "summary" in dashboard and "provider_diagnostics" in dashboard,
            "summary/provider_diagnostics present",
        )
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"FAIL admin_dashboard: {exc}")
        failures += 1

    try:
        release = get_json("/api/admin/release-readiness", admin=True)
        release_pass = (release.get("release_gate") or {}).get("pass") is True
        blocker_count = len((release.get("release_gate") or {}).get("blockers") or [])
        allow_unready = os.getenv("ALLOW_UNREADY_RELEASE_SMOKE", "false").lower() in {"1", "true", "on"}
        if allow_unready and not release_pass:
            print(f"WARN release_readiness: release_gate=false blockers={blocker_count} bypass=ALLOW_UNREADY_RELEASE_SMOKE")
        else:
            failures += not check(
                "release_readiness",
                release_pass,
                f"release_gate={release_pass} blockers={blocker_count}",
            )
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"FAIL release_readiness: {exc}")
        failures += 1

    if failures:
        print("RESULT=not_ready")
        return 1
    print("RESULT=ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
