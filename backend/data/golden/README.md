# Release Golden Labels

Place the human-adjudicated release golden set at:

```text
backend/data/golden/release_scenarios.jsonl
```

Each line must be one JSON object. The release gate requires at least 300 scenarios,
8 focus cities, 20% holdout split, consensus >= 0.6, and outputs for every mandatory
baseline.

Required fields:

```json
{
  "scenario_id": "ha_noi-first-time-001",
  "city": "ha_noi",
  "labels": ["lich_su", "dia_danh"],
  "ideal_place_ids": ["curated-hanoi-ho-guom", "curated-hanoi-den-ngoc-son"],
  "baseline_place_ids": {
    "bo_giai_cu": ["curated-hanoi-ho-guom"],
    "lich_mau_bien_tap": ["curated-hanoi-den-ngoc-son"],
    "ai_chung_khong_hoc_them": ["curated-hanoi-ho-guom"]
  },
  "annotator_count": 3,
  "consensus": 0.84,
  "split": "holdout"
}
```

Do not generate this file from the planner output. It must come from human review
or a separately managed expert annotation process.
