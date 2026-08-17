from app.pipeline.famous_score import (
    apply_hybrid_scores,
    grey_zone_rows,
    is_low_fame_place,
    llm_candidates,
    parse_llm_scores,
)


def test_low_fame_rules_catch_gates_cemeteries_and_private_gardens():
    assert is_low_fame_place("Cửa Hậu", ["city_gate"])
    assert is_low_fame_place("Nghĩa trang Liệt Sĩ", ["memorial"])
    assert is_low_fame_place("Green Garden", ["garden"])
    assert not is_low_fame_place("Đại Nội Huế", ["heritage"])
    assert not is_low_fame_place("Cầu Vàng", ["attraction"])


def test_wikipedia_and_heritage_outrank_raw_osm_tags():
    rows = [
        {
            "id": "osm-a",
            "name": "Cầu Vàng",
            "kind": "dia_danh",
            "tags": ["attraction"],
            "muc_uu_tien": 3,
        },
        {
            "id": "osm-b",
            "name": "Cửa Hữu",
            "kind": "di_tich",
            "tags": ["city_gate"],
            "muc_uu_tien": 3,
        },
        {
            "id": "osm-c",
            "name": "Green Garden",
            "kind": "cong_vien",
            "tags": ["garden"],
            "muc_uu_tien": 3,
        },
    ]
    scored = apply_hybrid_scores(
        rows,
        curated_keys=set(),
        wikipedia_names={"cau vang"},
        heritage_ids=set(),
        llm_scores={},
    )
    by_id = {row["id"]: row for row in scored}
    assert by_id["osm-a"]["muc_uu_tien"] == 1
    assert by_id["osm-a"]["bang_chung"] == "wikipedia"
    assert by_id["osm-b"]["muc_uu_tien"] == 3
    assert by_id["osm-b"]["bang_chung"] == "low_fame_rule"
    assert by_id["osm-c"]["bang_chung"] == "low_fame_rule"


def test_llm_may_only_score_ids_we_sent():
    scored = parse_llm_scores(
        {
            "scores": [
                {"id": "osm-real", "muc_uu_tien": 2, "ly_do": "bien noi tieng"},
                {"id": "invented", "muc_uu_tien": 1, "ly_do": "bi a"},
                {"id": "osm-bad", "muc_uu_tien": 9, "ly_do": "ngoai thang"},
            ]
        },
        {"osm-real"},
    )
    assert set(scored) == {"osm-real"}
    assert scored["osm-real"]["muc_uu_tien"] == 2


def test_llm_fills_only_the_grey_zone():
    rows = apply_hybrid_scores(
        [
            {"id": "osm-wiki", "name": "Chùa Thiên Mụ", "kind": "den_chua", "tags": [], "muc_uu_tien": 3},
            {"id": "osm-grey", "name": "Suối tiên Mũi Né", "kind": "dia_danh", "tags": ["attraction"], "muc_uu_tien": 3},
        ],
        curated_keys=set(),
        wikipedia_names={"chua thien mu"},
        llm_scores={"osm-grey": {"muc_uu_tien": 2, "ly_do": "doi cat / suoi du lich"}},
    )
    by_id = {row["id"]: row for row in rows}
    assert by_id["osm-wiki"]["bang_chung"] == "wikipedia"
    assert by_id["osm-wiki"]["muc_uu_tien"] == 1
    assert by_id["osm-grey"]["bang_chung"] == "llm"
    assert by_id["osm-grey"]["muc_uu_tien"] == 2
    assert [row["id"] for row in grey_zone_rows(rows)] == []
    assert llm_candidates(rows) == []


def test_curated_wins_even_if_a_name_looks_generic():
    rows = apply_hybrid_scores(
        [{"id": "curated-x", "name": "Cửa Hội", "kind": "dia_danh", "source": "curated", "tags": [], "muc_uu_tien": 3}],
        curated_keys={"cua hoi"},
    )
    assert rows[0]["muc_uu_tien"] == 1
    assert rows[0]["bang_chung"] == "curated"
