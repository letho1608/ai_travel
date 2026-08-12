from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    load_dotenv(ENV_FILE)
    ai_mode = os.getenv("AI_MODE", "mock").strip().lower()
    key_env = "API_KEY_GROQ" if ai_mode == "groq" else "API_KEY_DEEPSEEK"
    model_env = "TEN_MODEL_GROQ" if ai_mode == "groq" else "TEN_MODEL_DEEPSEEK"
    default_model = "llama-3.3-70b-versatile" if ai_mode == "groq" else "deepseek-v4-flash"
    api_key = os.getenv(key_env, "").strip()
    model = os.getenv(model_env, default_model).strip()
    base_url = os.getenv(
        "AI_BASE_URL",
        "https://api.groq.com/openai/v1" if ai_mode == "groq" else "https://api.deepseek.com",
    ).strip()

    print(f"AI_MODE={ai_mode}")
    print(f"{model_env}={model}")
    print(f"AI_BASE_URL={base_url}")

    if ai_mode == "mock":
        print("STATUS=mock")
        print("NEXT=Set AI_MODE=groq and API_KEY_GROQ in .env, then restart run.bat.")
        return 2
    if ai_mode not in {"groq", "deepseek"}:
        print(f"STATUS=unsupported ({ai_mode})")
        print("NEXT=Use AI_MODE=mock for local fallback, AI_MODE=groq for Groq, or AI_MODE=deepseek.")
        return 1
    if not api_key:
        print("STATUS=missing_api_key")
        print(f"NEXT=Set {key_env} in .env, then restart run.bat.")
        return 1

    print(f"STATUS=ready key_len={len(api_key)}")
    print("NEXT=Run run.bat, then verify /health and /api/admin/ai-quality.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
