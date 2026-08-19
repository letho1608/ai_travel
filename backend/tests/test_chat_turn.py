from app.pipeline import chat_turn, intent_parse
from app.pipeline.chat_turn import run_chat_turn


class SilentAI:
    def extract_planning_intent(self, _context: str, _locale: str = "vi") -> dict:
        return {}

    def compose_chat_reply(self, messages, intent, locale="vi") -> str:
        return ""


def _silence(monkeypatch):
    monkeypatch.setattr(chat_turn, "ai_adapter", SilentAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", SilentAI())


def test_chat_turn_acknowledges_named_place_instead_of_asking_city(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [{"role": "user", "content": "tôi muốn lên plan đi chùa yên tử"}],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert "destination" not in result["intent"]["missing_fields"]
    assert result["ready_to_plan"] is False
    assert "Yên Tử" in result["reply"]
    assert "Hà Nội" not in result["reply"]
    assert "Đà Nẵng" not in result["reply"]
    folded = result["reply"].casefold()
    assert "quảng ninh" in folded or "tâm linh" in folded or "núi" in folded


def test_chat_turn_uses_llm_to_introduce_yen_tu(monkeypatch):
    class LiveAI:
        def extract_planning_intent(self, _context, _locale="vi"):
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            return (
                "Yên Tử là danh thắng tâm linh trên núi ở Quảng Ninh, khí trời mát và yên. "
                "Bạn muốn đi khoảng mấy ngày?"
            )

    monkeypatch.setattr(chat_turn, "ai_adapter", LiveAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", LiveAI())
    result = run_chat_turn([{"role": "user", "content": "t muốn đi núi yên tử"}], "vi")
    assert result["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert result["reply"].startswith("Yên Tử là danh thắng")
    assert "mấy ngày" in result["reply"].casefold()
    assert "mấy người" not in result["reply"].casefold()


def test_chat_turn_expands_bare_day_count_after_destination(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi muốn lên plan đi chùa yên tử"},
            {"role": "assistant", "content": "Bạn đi bao lâu?"},
            {"role": "user", "content": "3"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert result["intent"]["parsed"]["duration_days"] == 3
    assert "duration" not in result["intent"]["missing_fields"]
    assert "people" in result["intent"]["missing_fields"]


def test_chat_turn_keeps_theme_only_destination_question(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn([{"role": "user", "content": "Tôi muốn đi chữa lành"}], "vi")
    assert result["intent"]["parsed"]["destination"] is None
    assert "destination" in result["intent"]["missing_fields"]
    assert result["ready_to_plan"] is False


def test_chat_turn_answers_stress_with_healing_places(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {
                "role": "assistant",
                "content": "Bạn muốn đi đâu lần này? Nếu chưa nghĩ ra, mình có thể chọn giúp — ví dụ Hà Nội, Đà Nẵng, Hội An.",
            },
            {"role": "user", "content": "tôi stress quá"},
        ],
        "vi",
    )
    assert result["intent"]["ask_topic"] == "healing"
    assert result["intent"]["parsed"]["primary_intent"] == "healing"
    assert "destination" in result["intent"]["missing_fields"]
    assert result["ready_to_plan"] is False
    folded = result["reply"].casefold()
    assert "đà lạt" in folded
    assert "sa pa" in folded
    assert "ninh bình" in folded
    assert "phú quốc" in folded
    assert "thông" in folded or "sương" in folded or "núi mây" in folded
    assert "chưa hiểu rõ" not in folded
    assert "số ngày" not in folded
    assert "số người" not in folded
    assert "vài giờ" not in folded


def test_chat_turn_repeated_tired_does_not_ask_people(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi mệt quá"},
            {
                "role": "assistant",
                "content": (
                    "Nghe bạn đang mệt. Đi chữa lành thì Đà Lạt, Ninh Bình thường yên. "
                    "Bạn muốn se lạnh, núi, hay biển?"
                ),
            },
            {"role": "user", "content": "mệt"},
        ],
        "vi",
    )
    folded = result["reply"].casefold()
    assert "mấy người" not in folded
    assert "hỏi lại cho rõ" not in folded
    assert "mệt" in folded or "nhẹ" in folded or "đà lạt" in folded or "ninh bình" in folded


def test_chat_turn_uses_llm_for_stress(monkeypatch):
    class LiveAI:
        def extract_planning_intent(self, _context, _locale="vi"):
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            return (
                "Nghe mệt quá thì mình nghĩ Đà Lạt hoặc Ninh Bình hợp để thở. "
                "Bạn muốn đi chữa lành ở đâu?"
            )

    monkeypatch.setattr(chat_turn, "ai_adapter", LiveAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", LiveAI())
    result = run_chat_turn([{"role": "user", "content": "tôi stress quá"}], "vi")
    assert result["reply"].startswith("Nghe mệt quá")
    assert "Đà Lạt" in result["reply"]


def test_chat_turn_comforts_instead_of_asking_days(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "hà nội có những chỗ nào chơi?"},
            {
                "role": "assistant",
                "content": "Ở Hà Nội nhiều chỗ hay — ví dụ Hồ Gươm. Bạn đang muốn đi bộ trong phố, thiên nhiên, hay ăn uống?",
            },
            {"role": "user", "content": "có thể an ủi tôi được không"},
        ],
        "vi",
    )
    folded = result["reply"].casefold()
    assert "mấy ngày" not in folded
    assert "muốn đi hà nội" not in folded
    assert "số ngày" not in folded


def test_chat_turn_clears_rejected_hanoi(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "hà nội có những chỗ nào chơi?"},
            {"role": "assistant", "content": "Ở Hà Nội nhiều chỗ hay — ví dụ Hồ Gươm."},
            {"role": "user", "content": "tôi stress quá"},
            {"role": "assistant", "content": "Hà Nội cũng hợp để nghỉ cho đỡ stress. Bạn muốn đi khoảng mấy ngày?"},
            {"role": "user", "content": "tôi không muốn đi hà nội"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"] is None
    folded = result["reply"].casefold()
    assert "mình hiểu bạn muốn đi hà nội" not in folded
    assert "mấy ngày" not in folded


def test_chat_turn_auto_picks_when_user_is_uncertain(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "Tôi muốn đi chữa lành"},
            {
                "role": "assistant",
                "content": (
                    "Bạn muốn đi chữa lành ở đâu? Mình gợi ý Đà Lạt, Sa Pa, Ninh Bình, Phú Quốc. "
                    "Chọn một điểm, hoặc nói 'bạn chọn giúp' để mình thiết kế hộ."
                ),
            },
            {"role": "user", "content": "đâu cũng được"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Đà Lạt"
    assert "destination" not in result["intent"]["missing_fields"]
    assert result["intent"]["auto_picked_destination"] is True
    assert "Đà Lạt" in result["reply"]
    assert "mấy ngày" in result["reply"].casefold()
    assert "Sa Pa" not in result["reply"]
    assert "Ninh Bình" not in result["reply"]
    assert "Phú Quốc" not in result["reply"]


def test_chat_turn_answers_hanoi_places_instead_of_asking_days(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [{"role": "user", "content": "hà nội có những chỗ nào chơi?"}],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Hà Nội"
    assert "destination" not in result["intent"]["missing_fields"]
    assert "duration" in result["intent"]["missing_fields"]
    assert result["intent"]["user_goal"] == "places"
    assert "Hồ Gươm" in result["reply"]
    assert result["reply"] != "Ok, mình hiểu bạn muốn đi Hà Nội. Bạn đi khoảng mấy ngày?"


def test_chat_turn_answers_dalat_places_without_question_mark(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn([{"role": "user", "content": "Đà lạt có chỗ nào chơi"}], "vi")
    assert result["intent"]["parsed"]["destination"]["name"] == "Đà Lạt"
    assert result["intent"]["user_goal"] == "places"
    folded = result["reply"].casefold()
    assert any(
        name in result["reply"]
        for name in ("Hồ Xuân Hương", "Đỉnh Langbiang", "Thung lũng Tình Yêu", "Chùa Linh Phước")
    )
    assert "mấy ngày" not in folded
    assert "bao lâu" not in folded
    assert "。" not in result["reply"]


def test_chat_turn_drops_duration_question_when_user_asks_places(monkeypatch):
    class LiveAI:
        def extract_planning_intent(self, _context, _locale="vi"):
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            last = (intent.get("last_user_message") or "").casefold()
            if "đà lạt" in last or "da lat" in last:
                return "Đà Lạt là nơi tuyệt vời để bạn ,  。 Bạn dự định đi trong bao lâu?"
            return (
                "Hà Nội có một không gian rất riêng, vừa cổ kính vừa hiện đại, "
                "thích hợp để bạn đi bộ chậm rãi và tìm lại sự bình yên. "
                "Bạn định dành bao nhiêu ngày cho chuyến đi này?"
            )

    monkeypatch.setattr(chat_turn, "ai_adapter", LiveAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", LiveAI())
    hanoi = run_chat_turn([{"role": "user", "content": "hà nội có những chỗ nào chơi?"}], "vi")
    assert "Hồ Gươm" in hanoi["reply"]
    assert "bao nhiêu ngày" not in hanoi["reply"].casefold()
    assert "mấy ngày" not in hanoi["reply"].casefold()

    dalat = run_chat_turn([{"role": "user", "content": "Đà lạt có chỗ nào chơi"}], "vi")
    assert "。" not in dalat["reply"]
    assert any(
        name in dalat["reply"]
        for name in ("Hồ Xuân Hương", "Đỉnh Langbiang", "Thung lũng Tình Yêu", "Chùa Linh Phước")
    )
    assert "bao lâu" not in dalat["reply"].casefold()


def test_chat_turn_answers_dalat_cautions_instead_of_place_list(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi không biết"},
            {"role": "assistant", "content": "Mình chọn Đà Lạt giúp bạn. Bạn muốn đi khoảng mấy ngày?"},
            {"role": "user", "content": "đi đà lạt thì chú ý những gì?"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Đà Lạt"
    assert result["intent"]["ask_topic"] == "tips"
    assert result["intent"]["user_goal"] == "answer"
    folded = result["reply"].casefold()
    assert "hồ xuân hương" not in folded
    assert "langbiang" not in folded
    assert "đi bộ trong phố" not in folded
    assert "mưa" in folded or "lạnh" in folded or "tháng" in folded


def test_chat_turn_drops_place_list_when_user_asks_cautions(monkeypatch):
    class LiveAI:
        def extract_planning_intent(self, _context, _locale="vi"):
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            return (
                "Ở Đà Lạt nhiều chỗ hay — ví dụ Hồ Xuân Hương, Đỉnh Langbiang, Chùa Linh Phước, Nhà thờ Con Gà. "
                "Bạn đang muốn đi bộ trong phố, thiên nhiên, hay ăn uống?"
            )

    monkeypatch.setattr(chat_turn, "ai_adapter", LiveAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", LiveAI())
    result = run_chat_turn([{"role": "user", "content": "đi đà lạt thì chú ý những gì?"}], "vi")
    folded = result["reply"].casefold()
    assert "đi bộ trong phố" not in folded
    assert "hồ xuân hương" not in folded
    assert "mưa" in folded or "lạnh" in folded or "tháng" in folded


def test_chat_turn_does_not_repeat_duration_when_user_repeats_the_question(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "hà nội có những chỗ nào chơi?"},
            {"role": "assistant", "content": "Ok, mình hiểu bạn muốn đi Hà Nội. Bạn đi khoảng mấy ngày?"},
            {"role": "user", "content": "tôi đang hỏi hà nội có những chỗ nào chơi mf"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Hà Nội"
    assert "Hồ Gươm" in result["reply"]
    assert result["reply"] != "Ok, mình hiểu bạn muốn đi Hà Nội. Bạn đi khoảng mấy ngày?"
    folded = result["reply"].casefold()
    assert "hồ gươm" in folded or "phố cổ" in folded


def test_chat_turn_answers_food_and_season_questions(monkeypatch):
    _silence(monkeypatch)
    food = run_chat_turn([{"role": "user", "content": "hà nội ăn gì ngon"}], "vi")
    assert food["intent"]["parsed"]["destination"]["name"] == "Hà Nội"
    assert food["intent"]["user_goal"] == "answer"
    assert food["reply"] != "Ok, mình hiểu bạn muốn đi Hà Nội. Bạn đi khoảng mấy ngày?"
    assert "Hà Nội" in food["reply"]

    season = run_chat_turn([{"role": "user", "content": "đà lạt đi mùa nào đẹp?"}], "vi")
    assert season["intent"]["parsed"]["destination"]["name"] == "Đà Lạt"
    assert season["intent"]["ask_topic"] == "season"
    folded = season["reply"].casefold()
    assert "tháng" in folded or "mùa" in folded
    assert "Langbiang" not in season["reply"]
    assert "mấy ngày để mình xếp lịch cụ thể hơn" not in season["reply"]


def test_chat_turn_answers_season_followup_without_repeating_place_script(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "Đà lạt thì nên đi mùa nào?"},
            {
                "role": "assistant",
                "content": "Ở Đà Lạt mình hay gợi ý Đỉnh Langbiang, Chùa Linh Phước. Bạn muốn đi khoảng mấy ngày để mình xếp lịch cụ thể hơn?",
            },
            {"role": "user", "content": "tôi đang hỏi mùa nào đẹp để đi đà lạt mà"},
        ],
        "vi",
    )
    assert result["intent"]["ask_topic"] == "season"
    assert "tháng" in result["reply"].casefold() or "mùa" in result["reply"].casefold()
    assert result["reply"] != (
        "Ở Đà Lạt mình hay gợi ý Đỉnh Langbiang, Chùa Linh Phước. Bạn muốn đi khoảng mấy ngày để mình xếp lịch cụ thể hơn?"
    )


def test_chat_turn_drops_model_thinking_leak(monkeypatch):
    class ThinkingAI:
        def extract_planning_intent(self, _context: str, _locale: str = "vi") -> dict:
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            return (
                "Here's a thinking process: Input is hà nội có những chỗ nào chơi? "
                "user_goal is places. GROUNDED_INTENT highlight_places: Hồ Gươm. "
                "Reply in Vietnamese. 2-5 short sentences."
            )

    monkeypatch.setattr(chat_turn, "ai_adapter", ThinkingAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", ThinkingAI())
    result = run_chat_turn([{"role": "user", "content": "hà nội có những chỗ nào chơi?"}], "vi")
    assert "thinking process" not in result["reply"].casefold()
    assert "GROUNDED_INTENT" not in result["reply"]
    assert "Hồ Gươm" in result["reply"]


def test_chat_turn_pivots_saigon_followup_to_beach(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "sài gòn thì đi đâu chơi"},
            {
                "role": "assistant",
                "content": (
                    "Ở TP.HCM mình hay gợi ý Nhà thờ Đức Bà, Phố đi bộ Nguyễn Huệ, "
                    "Trụ sở Ủy ban nhân dân Thành phố Hồ Chí Minh, Tượng đài Chủ tịch Hồ Chí Minh. "
                    "Bạn muốn đi khoảng mấy ngày để mình xếp lịch cụ thể hơn?"
                ),
            },
            {"role": "user", "content": "tôi muốn đi biển"},
        ],
        "vi",
    )
    assert result["intent"]["ask_topic"] == "beach"
    assert result["intent"]["parsed"]["destination"] is None
    folded = result["reply"].casefold()
    assert "biển" in folded
    assert "vũng tàu" in folded
    assert "Đức Bà" not in result["reply"]
    assert "Nguyễn Huệ" not in result["reply"]
    labels = [item["label"] for item in result["intent"]["suggestions"]]
    assert "Vũng Tàu" in labels


def test_chat_turn_suggests_mountain_destinations(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn([{"role": "user", "content": "tôi muốn đi leo núi"}], "vi")
    assert result["intent"]["ask_topic"] == "mountain"
    assert "Sa Pa" in result["reply"] or "Hà Giang" in result["reply"]
    assert "行程" not in result["reply"]


def test_chat_turn_strips_chinese_from_mountain_reply(monkeypatch):
    class MixedAI:
        def extract_planning_intent(self, _context, _locale="vi"):
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            return (
                "Leo núi ở Việt Nam thật sự rất thú vị. "
                "Hãy cho mình biết bạn muốn đi cùng bao nhiêu người và dự kiến行程 kéo dài bao lâu nhé."
            )

    monkeypatch.setattr(chat_turn, "ai_adapter", MixedAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", MixedAI())
    result = run_chat_turn([{"role": "user", "content": "tôi muốn đi leo núi"}], "vi")
    assert "行程" not in result["reply"]
    folded = result["reply"].casefold()
    assert "sa pa" in folded or "hà giang" in folded or "núi" in folded
    assert not (("người" in folded) and ("bao lâu" in folded or "mấy ngày" in folded))


def test_chat_turn_keeps_contextual_llm_reply_instead_of_place_script(monkeypatch):
    class LiveAI:
        def extract_planning_intent(self, _context, _locale="vi"):
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            last = (intent.get("last_user_message") or "").casefold()
            if "biển" in last:
                return (
                    "Gần Sài Gòn thì Vũng Tàu đi trong ngày cũng được. "
                    "Muốn nghỉ biển dài hơn thì Phú Quốc hoặc Nha Trang."
                )
            return "Hà Nội vui nhất khi đi bộ phố cổ buổi tối. Bạn thích nhịp chậm hay đông vui?"

    monkeypatch.setattr(chat_turn, "ai_adapter", LiveAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", LiveAI())
    places = run_chat_turn([{"role": "user", "content": "hà nội có những chỗ nào chơi?"}], "vi")
    assert "nhịp chậm hay đông vui" in places["reply"]
    assert "mấy ngày để mình xếp lịch cụ thể hơn" not in places["reply"]

    beach = run_chat_turn(
        [
            {"role": "user", "content": "sài gòn thì đi đâu chơi"},
            {"role": "assistant", "content": "Ở TP.HCM mình hay gợi ý Nhà thờ Đức Bà."},
            {"role": "user", "content": "tôi muốn đi biển"},
        ],
        "vi",
    )
    assert beach["reply"].startswith("Gần Sài Gòn")
    assert "Đức Bà" not in beach["reply"]


def test_chat_turn_auto_picks_on_i_dont_know(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "Tôi muốn đi chữa lành"},
            {"role": "assistant", "content": "Bạn muốn đi chữa lành ở đâu?"},
            {"role": "user", "content": "tôi không biết"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Đà Lạt"
    assert "destination" not in result["intent"]["missing_fields"]
    assert result["reply"] != (
        "Bạn muốn đi chữa lành ở đâu? Mình gợi ý Đà Lạt, Sa Pa, Ninh Bình, Phú Quốc. "
        "Chọn một điểm, hoặc nói 'bạn chọn giúp' để mình thiết kế hộ."
    )


def test_chat_turn_keeps_nhatrang_when_user_answers_a_number(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "sài gòn thì đi đâu chơi"},
            {"role": "assistant", "content": "Ở TP.HCM mình hay gợi ý Nhà thờ Đức Bà."},
            {"role": "user", "content": "tôi muốn đi biển"},
            {
                "role": "assistant",
                "content": (
                    "Nha Trang đẹp lắm, biển xanh cát trắng. "
                    "Bạn định đi mấy ngày và đi cùng bao nhiêu người để mình lên lịch trình chi tiết nhé?"
                ),
            },
            {"role": "user", "content": "2"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Nha Trang"
    assert result["intent"]["parsed"]["duration_days"] == 2
    assert result["intent"]["parsed"].get("people") in (None, 0)
    assert "people" in result["intent"]["missing_fields"]
    assert result["ready_to_plan"] is False
    assert "TP.HCM" not in result["reply"]
    assert "Nha Trang" in result["reply"]


def test_chat_turn_answers_beach_instead_of_duration_script(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "sài gòn thì đi đâu chơi"},
            {
                "role": "assistant",
                "content": (
                    "Bạn muốn chuyến đi kéo dài trong bao lâu? Có thể ghi 2 giờ, từ 9h đến 17h, "
                    "từ 20/8 đến 22/8, hoặc chọn: Vài giờ, Nửa ngày, Cả ngày, Nhiều ngày."
                ),
            },
            {"role": "user", "content": "thôi tôi muốn đi biển cơ"},
        ],
        "vi",
    )
    assert result["intent"]["ask_topic"] == "beach"
    folded = result["reply"].casefold()
    assert "biển" in folded
    assert "vũng tàu" in folded or "nha trang" in folded or "phú quốc" in folded
    assert "kéo dài trong bao lâu" not in folded
    assert "vài giờ" not in folded


def test_chat_turn_accepts_bare_two_as_days_after_how_many_days(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi muốn đi đà lạt"},
            {
                "role": "assistant",
                "content": (
                    "Sa Pa có mây núi, Ninh Bình yên như tranh, Phú Quốc biển xanh. "
                    "Bạn thấy mình hợp núi rừng, biển hay thành phố nhỏ? "
                    "Và bạn dự định đi trong bao nhiêu ngày để mình gợi ý cụ thể hơn nhé?"
                ),
            },
            {"role": "user", "content": "2"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Đà Lạt"
    assert result["intent"]["parsed"]["duration_days"] == 2
    assert result["intent"]["parsed"].get("people") in (None, 0)
    assert "duration" not in result["intent"]["missing_fields"]
    assert "people" in result["intent"]["missing_fields"]
    assert result["ready_to_plan"] is False
    folded = result["reply"].casefold()
    assert "kéo dài trong bao lâu" not in folded
    assert "vài giờ" not in folded
    assert "mấy người" in folded or "cùng ai" in folded or "một mình" in folded
    assert "ngày đầu" not in folded
    assert "ngày thứ" not in folded
    assert "buổi sáng" not in folded
    assert " và đi cùng" not in folded
    assert "và đi mấy người" not in folded


def test_chat_turn_asks_one_slot_at_a_time_for_yen_tu(monkeypatch):
    _silence(monkeypatch)
    first = run_chat_turn([{"role": "user", "content": "tôi muon đi núi yên tử"}], "vi")
    assert first["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert first["ready_to_plan"] is False
    assert "duration" in first["intent"]["missing_fields"]
    folded = first["reply"].casefold()
    assert "yên tử" in folded
    assert "quảng ninh" in folded or "tâm linh" in folded
    assert "mấy ngày" in folded or "bao lâu" in folded
    assert "bao nhiêu người" not in folded
    assert "mấy người" not in folded
    assert "ngày 1" not in folded
    assert "buổi sáng" not in folded

    second = run_chat_turn(
        [
            {"role": "user", "content": "tôi muon đi núi yên tử"},
            {"role": "assistant", "content": first["reply"]},
            {"role": "user", "content": "2"},
        ],
        "vi",
    )
    assert second["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert second["intent"]["parsed"]["duration_days"] == 2
    assert "people" in second["intent"]["missing_fields"]
    assert second["ready_to_plan"] is False
    folded = second["reply"].casefold()
    assert "yên tử" in folded
    assert "hạ long" not in folded
    assert "mấy người" in folded
    assert "ngày đầu" not in folded
    assert "buổi sáng" not in folded
    assert "lịch trình chi tiết" not in folded


def test_chat_turn_does_not_swap_yen_tu_for_ha_long_after_quang_ninh_intro(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi muốn đi yên tử"},
            {
                "role": "assistant",
                "content": (
                    "Yên Tử ở Quảng Ninh là danh thắng tâm linh trên núi, khí trời mát và yên, "
                    "hợp đi chậm để tĩnh tâm. Bạn muốn đi khoảng mấy ngày?"
                ),
            },
            {"role": "user", "content": "2 ngày"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert result["intent"]["parsed"]["duration_days"] == 2
    assert "people" in result["intent"]["missing_fields"]
    folded = result["reply"].casefold()
    assert "yên tử" in folded
    assert "hạ long" not in folded
    assert "mấy người" in folded


def test_chat_turn_keeps_ten_day_hanoi_answer(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi muốn đi du lịch hà nội"},
            {"role": "assistant", "content": "Hà Nội phố cổ, hồ và nhịp sống riêng. Bạn muốn đi khoảng mấy ngày?"},
            {"role": "user", "content": "10"},
            {"role": "assistant", "content": "Đi Hà Nội thì bạn đi mấy người?"},
            {"role": "user", "content": "2"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Hà Nội"
    assert result["intent"]["parsed"]["duration_days"] == 10
    assert result["intent"]["parsed"]["people"] == 2
    assert result["ready_to_plan"] is True


def test_chat_turn_treats_afternoon_window_as_duration(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "du lịch hà nội"},
            {"role": "assistant", "content": "Hà Nội phố cổ, hồ và nhịp sống riêng, hợp đi bộ khám phá. Bạn muốn đi khoảng mấy ngày?"},
            {"role": "user", "content": "15h đến 18h"},
        ],
        "vi",
    )
    parsed = result["intent"]["parsed"]
    assert parsed["destination"]["name"] == "Hà Nội"
    assert parsed["time_window"]["label"] == "15h–18h"
    assert "duration" not in (result["intent"]["missing_fields"] or [])
    assert "people" in result["intent"]["missing_fields"]
    assert result["intent"].get("user_goal") not in {"answer", "places"}
    folded = result["reply"].casefold()
    assert "câu hỏi về hà nội" not in folded
    assert "an ủi" not in folded
    assert "15h" in folded or "15h–18h" in folded or "khung" in folded
    assert "mấy người" in folded

    confused = run_chat_turn(
        [
            {"role": "user", "content": "du lịch hà nội"},
            {"role": "assistant", "content": "Hà Nội phố cổ, hồ và nhịp sống riêng. Bạn muốn đi khoảng mấy ngày?"},
            {"role": "user", "content": "15 giờ tới 18 giờ"},
            {"role": "assistant", "content": "Mình hiểu câu hỏi về Hà Nội."},
            {"role": "user", "content": "ủa cái gì đấy"},
        ],
        "vi",
    )
    folded = confused["reply"].casefold()
    assert "câu hỏi về hà nội" not in folded
    assert "an ủi" not in folded
    assert "mấy người" in folded or "mấy ngày" in folded


def test_chat_turn_treats_slash_dates_as_trip_days(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "du lịch hà nội"},
            {"role": "assistant", "content": "Hà Nội phố cổ, hồ và nhịp sống riêng, hợp đi bộ khám phá. Bạn muốn đi khoảng mấy ngày?"},
            {"role": "user", "content": "20/8 đến 21/8"},
        ],
        "vi",
    )
    parsed = result["intent"]["parsed"]
    assert parsed["destination"]["name"] == "Hà Nội"
    assert parsed["duration_days"] == 2
    assert not parsed.get("time_window")
    assert "duration" not in (result["intent"]["missing_fields"] or [])
    assert "people" in result["intent"]["missing_fields"]
    folded = result["reply"].casefold()
    assert "8h–21h" not in folded
    assert "8h-21h" not in folded
    assert "khung 8h" not in folded
    assert "2 ngày" in folded or "mấy người" in folded

    corrected = run_chat_turn(
        [
            {"role": "user", "content": "du lịch hà nội"},
            {"role": "assistant", "content": "Hà Nội phố cổ, hồ và nhịp sống riêng. Bạn muốn đi khoảng mấy ngày?"},
            {"role": "user", "content": "20/8 đến 21/8"},
            {"role": "assistant", "content": "Khung 8h–21h mình nhận rồi. Đi Hà Nội thì bạn đi mấy người?"},
            {"role": "user", "content": "không 20/8/ tới 21/8 mà"},
        ],
        "vi",
    )
    parsed = corrected["intent"]["parsed"]
    assert parsed["duration_days"] == 2
    assert not parsed.get("time_window")
    folded = corrected["reply"].casefold()
    assert "8h–21h" not in folded
    assert "khung 8h" not in folded
    assert "mấy người" in folded


def test_chat_turn_ok_keeps_collecting_people_instead_of_restarting(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi muon đi núi yên tử"},
            {"role": "assistant", "content": "Ok, mình hiểu bạn muốn đi Yên Tử. Bạn đi khoảng mấy ngày?"},
            {"role": "user", "content": "2"},
            {
                "role": "assistant",
                "content": (
                    "Dưới đây là gợi ý lịch trình chi tiết cho bạn: "
                    "Ngày 1 buổi sáng xuất phát từ Hà Nội. Buổi chiều leo núi Yên Tử."
                ),
            },
            {"role": "user", "content": "ok"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert result["intent"]["parsed"]["duration_days"] == 2
    assert "people" in result["intent"]["missing_fields"]
    assert result["ready_to_plan"] is False
    assert result["intent"].get("user_goal") not in {"answer", "places"}
    folded = result["reply"].casefold()
    assert "mình hiểu câu hỏi về yên tử" not in folded
    assert "mấy người" in folded
    assert "vài giờ" not in folded
    assert "nửa ngày" not in folded


def test_chat_turn_bare_two_after_companion_question_is_people(monkeypatch):
    _silence(monkeypatch)
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi muốn đi yên tử"},
            {
                "role": "assistant",
                "content": "Để lên kế hoạch tốt nhất, bạn dự định đi trong bao nhiêu ngày và đi cùng bao nhiêu người?",
            },
            {"role": "user", "content": "2"},
            {
                "role": "assistant",
                "content": (
                    "Đi Yên Tử 2 ngày là lịch trình rất thoải mái, vừa đủ để bạn thong thả tham quan. "
                    "Ngày đầu tiên bạn có thể đi từ Hà Nội lên chùa Đồng. "
                    "Ngày thứ hai hãy dành thời gian cho chùa Bảo Sái và chùa Giải Oan. "
                    "Bạn đi cùng gia đình, bạn bè hay một mình để mình gợi ý chỗ ở và phương tiện phù hợp hơn?"
                ),
            },
            {"role": "user", "content": "2"},
        ],
        "vi",
    )
    assert result["intent"]["parsed"]["destination"]["name"] == "Yên Tử"
    assert result["intent"]["parsed"]["duration_days"] == 2
    assert result["intent"]["parsed"]["people"] == 2
    assert "people" not in result["intent"]["missing_fields"]
    assert result["ready_to_plan"] is True
    folded = result["reply"].casefold()
    assert "mình nhận 2 ngày" not in folded
    assert "bạn đi mấy người" not in folded


def test_chat_turn_drops_itinerary_essay_while_people_missing(monkeypatch):
    class EssayAI:
        def extract_planning_intent(self, _context, _locale="vi"):
            return {}

        def compose_chat_reply(self, messages, intent, locale="vi") -> str:
            return (
                "Đi Yên Tử 2 ngày là lịch trình rất thoải mái. "
                "Ngày đầu tiên lên chùa Đồng, ngày thứ hai đi chùa Bảo Sái."
            )

    monkeypatch.setattr(chat_turn, "ai_adapter", EssayAI())
    monkeypatch.setattr(intent_parse, "ai_adapter", EssayAI())
    result = run_chat_turn(
        [
            {"role": "user", "content": "tôi muốn đi yên tử"},
            {
                "role": "assistant",
                "content": "Bạn dự định đi trong bao nhiêu ngày và đi cùng bao nhiêu người?",
            },
            {"role": "user", "content": "2"},
        ],
        "vi",
    )
    assert result["ready_to_plan"] is False
    assert "people" in result["intent"]["missing_fields"]
    folded = result["reply"].casefold()
    assert "ngày đầu" not in folded
    assert "chùa đồng" not in folded
    assert "mấy người" in folded or "cùng ai" in folded or "một mình" in folded
