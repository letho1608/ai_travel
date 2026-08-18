# 01 — Kiểm kê hiện trạng lớp regex-NLU (coverage, lỗ hổng, chi phí bảo trì)

**Lane:** 1/4 — regex audit. Không sửa code, chỉ đọc và kiểm kê.
**Phạm vi đọc:** `frontend/components/Planner.tsx` (720 dòng, đọc 100%), `backend/app/pipeline/planner.py` (4432 dòng, đọc toàn bộ phần NLU liên quan: 40–196, 249–352, 424–549, 723–754, 1029–1400, 1516–1580, 1682–1790, 3435–3533), `backend/app/routers/plans.py` (36–51, 135–179, 640–753), `backend/app/text_utils.py` (10 dòng), `backend/app/services/ai.py` (458 dòng), `backend/app/schemas.py` (1–70).
**Không phát hiện prompt-injection/chỉ thị nhắm agent** trong bất kỳ file nào đã đọc.

---

## 1. Kiến trúc tổng quan của lớp NLU hiện tại

Luồng parse hiện tại không phải "1 tầng NLU" mà là **4 tầng regex rời rạc**, mỗi tầng một tác giả, một quy chuẩn normalize khác nhau:

| Tầng | Vị trí | Input | Output | Normalize |
|---|---|---|---|---|
| A. Chat form frontend | `Planner.tsx:123-378` | câu user gõ | `thoi_luong`, `so_nguoi`, `ngan_sach`, `ngay_di`, `location`, gating hỏi-lại | NFD-strip + lowercase, **giữ nguyên `đ`** (`Planner.tsx:123-125`) |
| B. Timing backend | `planner.py:158-352` | `request.context` đã được FE nhồi thêm text | giờ bắt đầu, số phút, số ngày, ngày bắt đầu | `ascii_fold`: NFD-strip + **`đ→d`** (`text_utils.py:3-10`) |
| C. Intent/destination backend | `planner.py:1066-1237` | context | tags, profiles, điểm đến, dislike | `ascii_fold` |
| D. Refine backend | `plans.py:41-51, 668-691` | message tinh chỉnh | `so_nguoi`, `ngan_sach`, cờ swap | **KHÔNG fold** — match trực tiếp trên text có dấu |

Hệ quả cấu trúc quan trọng nhất: **cùng một câu tiếng Việt đi qua 3 bộ normalize khác nhau** (A fold-giữ-đ, B/C fold-đổi-đ, D không fold), nên các tầng bất đồng nhất với nhau về việc "câu này có nghĩa gì". AI_MODE=offline → `extract_request_intent` trả `{}` (`ai.py:77-78`), nghĩa là tầng C chỉ còn `_rule_preference_fields`/`_disliked_profiles` — toàn bộ phần "định tính" trông chờ vào regex.

---

## 2. Kiểm kê từng pattern / nhánh

### 2.1 Frontend — `Planner.tsx`

| # | Pattern / logic | Dòng | Parse được gì | Ghi chú |
|---|---|---|---|---|
| F1 | `normalizeText` | 123-125 | NFD-strip + lowercase | **Không đổi `đ→d`** — khác backend |
| F2 | `DESTINATION_LOCATIONS` — 18 regex `\b(...)\b` | 14-33 | 18 thành phố, lấy tọa độ | thiếu alias "thu do", "thanh pho ngan hoa", "quang nam", "hoa lu", "kien giang", "meo vac", "dat cang"... so với backend |
| F3 | `isUncertainReply` | 45-48 | câu trả lời "không biết" | phục vụ fallback mặc định |
| F4 | `inferClockRange` | 127-140 | "từ 9h đến 17h", "luc 8 gio ..." | regex :130 bắt phút `(?:[:h.]\d{2})?` nhưng **không capture, vứt bỏ phút** (chỉ dùng `Number(match[1])`); span 45p–16h |
| F5 | `hourWithMeridiem` | 142-147 | am/pm/sáng/chiều | ổn |
| F6 | `inferHourSpan` labeled | 151-155 | "2 giờ", "1.5 tieng", "giờ đồng hồ" | range 0.75–12h |
| F7 | `inferHourSpan` compact | 156-159 | "3h" | 1–12h |
| F8 | `inferHourSpan` word | 161-168 | "một giờ"…"năm giờ", "one hour"… | **chỉ 1–5**; "sáu giờ" trượt dù BE có |
| F9 | `parseSlashDate` | 171-176 | dd/mm(/yy) | validate rollover |
| F10 | `inferDateRange` slash-range | 181-194 | "20/8 đến 22/8" | cap 30 ngày; **không parse ngày đơn** ("ngày 20/8" trượt) |
| F11 | `inferDateRange` month-days | 195-204 | "từ ngày 5 đến ngày 7" (tháng hiện tại) | cap **5 ngày** — khác backend cap 30 (`planner.py:341`) |
| F12 | `DAY_COUNT_WORDS` | 214-225 | "một ngày"…"mười ngày" | 10 dòng; chỉ FE có, BE không có bản tương đương |
| F13 | `WEEK_COUNT_WORDS` | 227-232 | "một tuần"…"bốn tuần" | max 28 ngày |
| F14 | `inferDayCount` | 234-251 | `\d tuần/ngày`, word-days, date-range, "2,2" pair, số trần | `\d tuan` yêu cầu số đứng trước → "tuần sau" trượt |
| F15 | `inferDuration` keyword | 253-271 | "vài giờ", "nửa ngày", "cuối tuần"→ca_ngay, "nhieu ngay"... | "cuối tuần" map thành **1 ngày** (:269) |
| F16 | `inferPairedPeople` | 277-282 | input đúng dạng "2,2" / "2 2" | chỉ hoạt động ở slot hỏi đáp |
| F17 | `inferPeople` labeled | 286-299 | `\d + (nguoi/dua/con/tre em/pax/...)` | ≥2 match thì **cộng tổng** → trẻ em = người lớn, không phân loại |
| F18 | `inferPeople` wordMap | 300-313 | "một người"…"ten people" | **không có "đứa/cái/thằng/con"** → "hai đứa" trượt trong khi "2 đứa" trúng |
| F19 | `vo chong/couple → 2` | 314 | cặp đôi | chỉ chạy khi chưa có labeled match nào |
| F20 | `hasDestination` / `destinationLocation` | 331-339 | gating hỏi điểm đến + tọa độ | dùng F2; miss → fallback DEFAULT_HANOI (:13) |
| F21 | `stripBareCounts` | 345-353 | bỏ dòng chỉ chứa số | vệ sinh transcript |
| F22 | `inferBudget` triệu | 357-361 | `\d (trieu/trien/tr)` | clamp 50k–100M |
| F23 | `inferBudget` nghìn | 362-366 | `\d (nghin/ngan/k)` | nhánh `nghìn` **dead** vì input đã strip dấu |
| F24 | `inferBudget` đồng | 367-376 | `1.000.000 d/dong/đ/vnd`, `500000đ` | nhánh `đ` sống vì `đ` không bị fold |
| F25 | `composeRequestContext` | 380-405 | nhồi "X ngày, Y người" vào context gửi BE | BE sống nhờ format serialize này |
| F26 | flow `submit`/`answer*` | 517-630 | hỏi lần lượt duration→destination→people | thứ tự cứng |

### 2.2 Backend — `planner.py`

| # | Pattern / logic | Dòng | Parse được gì | Ghi chú |
|---|---|---|---|---|
| B1 | `LIMITS` | 50-56 | default phút/ngày theo `thoi_luong` | |
| B2 | `_CLOCK_RANGE_RE` | 158-167 | "từ 9h đến 17h" + phút | bản FE (F4) là bản **mất phút** của chính regex này |
| B3 | `_HOUR_SPAN_RE` | 168-171 | "2 giờ", "1,5 giờ" | |
| B4 | `_HOUR_COMPACT_RE` | 172 | "3h" | |
| B5 | `_HOUR_WORD` | 173-184 | "một giờ"…"sáu giờ" + en 1-4 | không có "bảy/tám/chín/mười giờ" |
| B6 | `night_shift` | 290-300 | "8h tối đến 11h đêm" | chỉ backend có; FE không biết start_time đêm |
| B7 | `_DATE_RANGE_RE` | 185-192 | dd/mm(–dd/mm), tự đẩy năm nếu quá khứ :311-313 | ngày đơn không hỗ trợ |
| B8 | `_DAY_RANGE_RE` | 193-196 | "từ ngày X đến ngày Y" | cap 30 (`planner.py:341`) — FE cap 5 |
| B9 | `labeled_days` | 346-348 | "\d+ ngay/days" | `\d` ≥2; **"hai ngày" không parse** ở backend |
| B10 | `_trip_timing` clamp | 350-351 | `thoi_luong≠nhieu_ngay` → days=1 | |
| B11 | `FOCUS_DESTINATIONS` | 440-549 | 18 điểm đến + aliases | mỗi cái match bằng word-boundary regex :1103 |
| B12 | catalog scan fallback | 1105-1149 | tên/area bất kỳ trong PLACES | ≥4 ký tự, score theo kind, threshold ≥6 |
| B13 | `relevant_tags` | 1066-1075 | unigram + bigram + trigram (folded, `_` join) | so **exact-match** với term list |
| B14 | `INTENT_PROFILES` | 723-754 | 6 profile: hanoi_highlights, coffee, food, culture, night, walk | term tiếng Anh/Việt lẫn lộn |
| B15 | `SEMANTIC_TAG_ALIASES` | 1045-1053 | map tag→nhóm ngữ nghĩa | chứa token đơn `gia`, `em`, `dinh`, `chua` → false positive ("giá rẻ" → tag `tre_em`) |
| B16 | `DISLIKE_PREFIXES` | 1203-1206 | 12 prefix dislike | thiếu "hong/hổng thích", "k thèm", "ngại" |
| B17 | `_disliked_profiles` | 1209-1217 | prefix + **đúng từ term của profile** | "không thích hải sản" trượt (hai_san không là term :734-738) |
| B18 | `_is_place_disliked` keyword núi | 1232-1235 | "khong thich/tranh leo nui/nui/trekking/di bo nhieu/mo hoi" | chỉ 2 prefix; "sợ leo núi" trượt dù "so" ∈ DISLIKE_PREFIXES |
| B19 | `_rule_dislike_fields` regex tự do | 1307-1310 | "không thích X" tự do (chỉ báo cáo, **không filter**) | chạy trên text **có dấu** → "khong thich" (không dấu) trượt ở đây nhưng trúng B17 |
| B20 | `max_places` | 1339 | "toi da/khong qua/qua N diem/cho/dia diem" | chỉ lưu vào understanding, không thấy áp cap thực tế ở `choose_candidates` |
| B21 | `VIETNAM_HOLIDAY_WINDOWS` | 1055-1059 | chú thích nếu ngày đi rơi vào cửa sổ lễ | Tết hardcode 20/1–20/2; **không dùng để parse "đi dịp tết"** |
| B22 | `_title_motif` | 84-103 | 8 nhóm từ khóa motif tiêu đề | bản sao thứ 3 của keyword lists |
| B23 | `_wants_night/_wants_coffee/_wants_old_quarter` | 1784-1789, 3435-3441 | cờ hành vi từ tags | |
| B24 | `_destination_context` | 1152-1165 | ghi đè tọa độ FE gửi | backend tự cứu khi FE gửi DEFAULT_LOCATION |

### 2.3 Backend — refine `plans.py`

| # | Pattern | Dòng | Parse được gì | Ghi chú |
|---|---|---|---|---|
| R1 | `SWAP_INTENT` | 41-46 | "đổi/thay/replace..." 19 ngôn ngữ | yêu cầu **có dấu** ("doi" trượt) |
| R2 | `PEOPLE_INTENT` | 47-51 | `\d + người/people...` | "2 nguoi" (không dấu) trượt |
| R3 | budget refine | 675-683 | "ngân sách/dưới/tối đa + số + k/nghìn/triệu" | **không fold** → "ngan sach 2 trieu" trượt |
| R4 | cheaper/move-less/cafe | 684-690 | cờ append text vào context | đã fold; append tiếng Anh |

---

## 3. Ví dụ thất bại thực tế (≥25)

Chuỗi "chuẩn" cần parse: *"cuối tuần 2 đứa nhỏ đi đà lạt né mưa, 1 triệu"* → FE parse được duration (`cuoi tuan`→`ca_ngay`, F15), người (`2 dua`), tiền (`1 trieu`), nhưng **`hasDestination` trượt vì chữ `đ` không được fold (F1/F2)** → hỏi lại "Bạn muốn đi đâu?" dù câu đã có điểm đến. Đó là triệu chứng của vấn đề lớn nhất bên dưới.

| # | Input | Kỳ vọng | Kết quả thực tế | Nguyên nhân (file:line) | Mức |
|---|---|---|---|---|---|
| 1 | "đi **đà lạt** cuối tuần" | nhận Đà Lạt | FE hỏi lại điểm đến; `location` gửi đi = Hà Nội | `Planner.tsx:124` không fold `đ`; `:24` | **Blocker** |
| 2 | "**đà nẵng** 2 ngày" | nhận Đà Nẵng | như trên | `Planner.tsx:17` vs `:124` | **Blocker** |
| 3 | "**đồng hới** chơi 1 ngày" | nhận Quảng Bình | trượt FE | `Planner.tsx:30` | Blocker |
| 4 | "đi **thành phố ngàn hoa** 2 ngày" | backend có alias | FE hỏi lại điểm đến (alias chỉ có BE) | FE thiếu alias vs `planner.py:475` | High |
| 5 | "**tuần sau** đi nha trang" | thứ 7/CN kế tiếp | không ra ngày, hỏi duration | không có relative-date nào (`Planner.tsx:234-251`) | High |
| 6 | "**tháng 6** vi vu sapa" | tháng 6 năm nay | trượt hoàn toàn | không branch tên tháng | High |
| 7 | "**2/9 này** lên hà giang" | ngày 2/9 | trượt (chỉ parse *range* dd/mm) | `Planner.tsx:181-183` | High |
| 8 | "**mai** rảnh, làm chuyến hà nội" | ngày mai | trượt | không có "mai/hôm nay" | High |
| 9 | "**thứ bảy tuần này** đi vũng tàu" | thứ 7 gần nhất | trượt | không có tên thứ | High |
| 10 | "đi đà lạt **3n2đ**" | 3 ngày 2 đêm | hỏi duration | cần literal "ngay" (`planner.py:346`) | High |
| 11 | "chơi **2 ngày rưỡi**" | 2.5 ngày | hỏi duration | không phân số ngày | Medium |
| 12 | "**sáng đi chiều về**" | nửa ngày | hỏi duration | F15 chỉ match "nua ngay" literal | Medium |
| 13 | "đi **trong ngày**" | 1 ngày | hỏi duration | không branch | Medium |
| 14 | "**xuyên đêm** ở nha trang" | khung đêm | FE hỏi; BE cũng cần số giờ | `planner.py:290` cần `\d` | Medium |
| 15 | "**vợ chồng mình và 2 đứa nhỏ**" | 4 (hoặc 2+2) | `so_nguoi=2`, mất con | F17 chỉ cộng `\d+đơn vị`, F19 không chạy khi đã có label | High |
| 16 | "**hai đứa** mình đi đà lạt" | 2 | hỏi mấy người | F18 wordMap thiếu "dua" (có ở F17) | High |
| 17 | "đi **1 mình**" | 1 | hỏi mấy người | F18 cần "mot + nguoi/ban/khach" | Medium |
| 18 | "**nhóm 5 người lớn 2 trẻ em**" | 5+2 có phân loại | =7, trẻ em tính như người lớn | F17 cộng dồn; schema không có trẻ em | Medium |
| 19 | "**gia đình mình** đi chơi" | family intent | không có người, không có tag gia_dinh đáng tin | F18; B15 aliased chỉ khi có số | Low |
| 20 | "ngân sách **2 triệu rưỡi**" | 2.5M | =2.0M, mất "rưỡi" | F22 bắt "2 trieu" | Medium |
| 21 | "**hai triệu** cho 2 người" | 2M | default 1M | F22 chỉ nhận số | High |
| 22 | "tầm **5 củ**" | 5M | default 1M | slang không có | Medium |
| 23 | "**0 đồng** / miễn phí" | budget 0 | không parse được; schema chặn `ge=50_000` | F22 + `schemas.py:33` | Medium |
| 24 | "budget **1 million VND**" | 1M | parse trượt, sống nhờ default trùng số | F22 thiếu "million" | Low |
| 25 | "**miền Tây** 2 ngày" | vùng ĐBSCL | hỏi điểm đến | chỉ 18 thành phố, không có vùng | High |
| 26 | "đi **biển gần Sài Gòn**" | biển lân cận | hỏi điểm đến | "bien" không là destination | High |
| 27 | "**nha trang hay đà lạt cũng được**" | cần disambiguate/hỏi chọn | FE chọn Nha Trang theo thứ tự mảng | `Planner.tsx:14-33` `.find()` | Medium |
| 28 | "xứ sở sương mù / **phố núi**" | Đà Lạt | hỏi điểm đến | không có biệt danh | Medium |
| 29 | "đi **đà lặt** 2 ngày" | typo Đà Lạt | hỏi điểm đến, không fuzzy | regex exact | High |
| 30 | "**ddi choi cuoi tuan**" (telex thừa) | cuối tuần | trượt duration | regex exact | Low |
| 31 | "**hổng thích** leo núi" | dislike núi | không filter | B16 thiếu "hong"; B18 chỉ "khong thich/tranh" | Medium |
| 32 | "**sợ đi bộ nhiều**" | giảm walking | không filter | B18 :1233 không nhận prefix "so" | Medium |
| 33 | "ghét **chỗ đông người**" | né nơi đông | chỉ hiện trong understanding, không lọc | B17 cần term profile; B18 ngoài danh sách | Medium |
| 34 | "**né mưa** / không thích ướt" | ưu tiên trong nhà khi mưa | không có semantic nào | B15/B17 không có mưa | High |
| 35 | "đừng cho **tụi nhỏ** đi biển" | né biển cho trẻ | không parse được cấu trúc phủ định phức | giới hạn cố hữu regex | High |
| 36 | "tối đa **5 điểm đến** thôi" | cap 5 | B20 lưu field nhưng không áp cap ở `choose_candidates:3444-3532` | `planner.py:1339` vs `:3494` | Medium |
| 37 | "**dịp tết** đi sapa" | ngày Tết thật | trượt; nếu tự chọn ngày rơi vào 20/1–20/2 thì được chú thích | B21 không phải parser | High |
| 38 | "**từ 7g30 đến 11g**" (kiểu miền Nam "g") | 7:30–11:00 | hỏi lại khung giờ | B2 chỉ nhận `[:h.]` | Medium |
| 39 | "khoảng **7 giờ** tối bắt đầu" | start 19h | start mặc định 8h00 | B5 thiếu "bay gio"; không có "giờ tối" | Medium |
| 40 | refine: "**ngan sach 2 trieu**" (gõ không dấu) | đổi ngân sách | giữ nguyên | R3 không fold (`plans.py:675-678`) | High |

(40 ví dụ; 25+ theo yêu cầu. Các câu có dấu chuẩn như "Hà Nội 2 giờ 2 người 1 triệu" đều trúng — lớp này chỉ ổn với input "sạch, đủ dấu, đúng từ khóa".)

---

## 4. Coverage theo lớp input (ước lượng trung thực)

Ước lượng dựa trên việc liệt kê cách nói tự nhiên thường gặp trong tiếng Việt chat (viết tắt, không dấu, số chữ, relative date, slang) so với những gì regex bắt được.

| Lớp | Coverage ước lượng | Lý do |
|---|---|---|
| Duration/thời lượng | **~35-40%** | Chỉ bắt: số+đơn vị ("2 giờ/3 ngày"), range giờ, range dd/mm, vài keyword literal. Trượt: relative ("tuần sau", "tháng 6", "mai", "thứ 7"), số chữ >10 ở backend ("hai ngày" BE chịu), phân số, idiom ("sáng đi chiều về"), viết tắt ("3n2đ"). |
| Số ngày | **~40%** | FE khá hơn (word-days một→mười, F12) nhưng BE chỉ hiểu `\d+ngày` (B9) và phụ thuộc FE nhồi text (F25) — parse không độc lập. |
| People | **~35%** | `\d+đơn vị` tốt; word-number thiếu "đứa" (F18); "1 mình", "vợ chồng và 2 con" sai ngữ nghĩa (F17/F19); không phân biệt người lớn/trẻ em ở schema. |
| Budget | **~25-30%** | `\d+(trieu/tr/nghin/k)` + format dấu chấm phẩy. Trượt: số chữ ("hai triệu" — rất phổ biến khi nói), "rưỡi", slang ("củ", "lít", "xị"), "0 đồng", USD, "ngân sách thoải mái". Backend generate **không parse budget từ context chút nào** — chỉ FE (F22) và refine (R3, không fold). |
| Destination | **~50-60%** câu *có nêu tên thành phố lớn*, **~0%** cho phần còn lại | 18 thành phố cover nhu cầu phổ biến; nhưng (a) bug `đ` làm chính "Đà Lạt/Đà Nẵng" chuẩn trượt FE; (b) không có vùng ("miền Tây", "Tây Bắc"), huyện/đảo nhỏ, biệt danh, "biển gần X"; (c) multi-destination không xử lý. Backend catalog scan (B12) gỡ được một phần nhờ đối chiếu PLACES nhưng chỉ cho địa danh có trong kho. |
| Datetime tuyệt đối | **~15-20%** | Chỉ dd/mm range. Ngày đơn, tên tháng, tên thứ, tên lễ, âm lịch: 0%. Trong chat tự nhiên, relative date chiếm đa số cách hẹn ngày → đây là lớp tệ nhất. |
| Dislike | **~10-20%** | Bắt được "không thích/không muốn/tránh/sợ/ghét/dị ứng với + đúng từ term profile" (B16-B17). Trượt: phủ định gián tiếp, dislike ngoài 6 profile ("hải sản", "đông người", "mưa", "di chuyển xa"), viết tắt ("k thích", "hok"), và nhánh raw-text (B19) bất đồng normalize với nhánh folded (B17). Quan trọng hơn: dislike free-text **chỉ để báo cáo, không lọc** (`planner.py:1307-1311` vs `_is_place_disliked:1220-1236`). |
| Sở thích/intent | **~25-35%** | `relevant_tags` (B13) unigram/bigram/trigram exact-match so với 6 profile (B14): "cà phê", "ăn ngon", "bảo tàng", "chợ đêm" trúng. Trượt: đồng nghĩa ngoài list ("uống trà chanh" ≠ cafe), tiếng Anh lẻ ("brunch"), và token đơn gây false positive (`gia`→`tre_em`, B15). |

**Kết luận phần này:** với input chat tự nhiên, tỷ lệ parse đúng trọn vẹn một câu phức hợp (điểm đến + thời gian tương đối + người + tiền + dislike) là rất thấp — ước <20%. Hệ thống "sống" được là nhờ chuỗi hỏi-lại (duration→destination→people, `Planner.tsx:517-630`) và default (budget 1M, ngày 1, Hanoi). Regex hiện tại đóng vai trò *tăng tốc input sạch*, không phải *hiểu ngôn ngữ*.

---

## 5. Chi phí bảo trì

### 5.1 Thêm 1 cách nói mới tốn bao nhiêu chỗ?

- **Cách nói thời lượng mới** (vd "nửa buổi"): sửa FE (`Planner.tsx:149-169` + `:253-271`) + BE (`planner.py:158-184` hoặc `:260-277`) + test (`test_pipeline.py:132-172`) → **3-4 chỗ, 2 ngôn ngữ, 2 bộ normalize**.
- **Thành phố mới**: `DESTINATION_LOCATIONS` (`Planner.tsx:14-33`) + `FOCUS_DESTINATIONS` (`planner.py:440-549`) + `SEASONAL_TOURISM_POLICY` (`planner.py:561-652`) + `PROVINCE_HIGHLIGHT_MAP` (`planner.py:1667,1711`) + chip suggestion (`Planner.tsx:667`) → **4-5 chỗ**. Quên 1 chỗ = frontend hỏi lại điểm đến dù backend hiểu (bug hiện hữu với "thành phố ngàn hoa", ví dụ #4).
- **Dislike mới**: `DISLIKE_PREFIXES` + term profile + có thể keyword list `_is_place_disliked:1232` → **2-3 chỗ**, và thường phải thêm profile mới vào `INTENT_PROFILES` thì mới có hiệu lực lọc.

### 5.2 Logic trùng lặp FE/BE (bảng song trùng)

| Logic | Frontend | Backend | Lệch nhau |
|---|---|---|---|
| Clock range | `Planner.tsx:129-131` | `planner.py:158-167` | FE **vứt phút**, BE giữ phút |
| Hour span | `Planner.tsx:151` | `planner.py:168-171` | cùng ý tưởng, code riêng |
| Compact hour | `Planner.tsx:156` | `planner.py:172` | |
| Hour words | `Planner.tsx:161-168` (1-5, có "bon/ba") | `planner.py:173-184` (1-6, en) | **khác tập từ** |
| Date range | `Planner.tsx:181-194` | `planner.py:185-192,302-318` | FE cap 30, month-days FE cap 5 vs BE cap 30 (`planner.py:341`) |
| Day words | `Planner.tsx:214-225` | *không có* | BE phụ thuộc FE serialize (`Planner.tsx:380-404`) |
| Week words | `Planner.tsx:227-232` | *không có* | như trên |
| Normalize | `Planner.tsx:123-125` | `text_utils.py:6-10` | **`đ`: BE→d, FE giữ** |
| Budget | `Planner.tsx:355-378` | `plans.py:675-683` | hai regex khác hẳn; refine không fold |
| People | `Planner.tsx:286-315` | `plans.py:47-51` | BE chỉ có ở refine; khác đơn vị |
| Destination list | `Planner.tsx:14-33` | `planner.py:440-549` | BE nhiều alias hơn FE |

Chi phí tiềm ẩn lớn nhất nằm ở dòng `composeRequestContext` (`Planner.tsx:380-405`): backend `_trip_timing` "hiểu" được "hai ngày" **là vì frontend đã dịch ra "2 ngày" nhồi vào context** (kèm guard `alreadyDays` :401). Gọi API trực tiếp với "đi hai ngày" → backend trả days=1. Đây là coupling ngầm, sửa format FE sẽ phá BE không có test nào bắt được.

---

## 6. Dead code / wiring yếu / lệch cấu trúc

1. **`_is_place_disliked` đã được wire** (`planner.py:3462` trong `choose_candidates`) — không dead. Nhưng nhánh keyword `:1232-1235` chỉ nhận 2 prefix "khong thich/tranh", **bỏ qua 10 prefix còn lại** trong `DISLIKE_PREFIXES` (:1203) → "sợ leo núi" không lọc (ví dụ #32). **High.**
2. **B19 `_rule_dislike_fields` free-text không có hiệu lực hành vi** — dislike tự do chỉ vào `dau_vao_da_hieu` làm trưng bày (`planner.py:1348-1369`), lịch vẫn xếp bình thường. Kết hợp với việc B17 chỉ nhận term profile, phần lớn dislike thực tế là *trang trí*. **High.**
3. **INTENT_PROFILES: không profile nào chết hẳn** — cả 6 được dùng qua `_intent_profiles` (:1175), `_wants_*` (:1784-1789), `_rule_preference_fields` (:1293). Nhưng `hanoi_highlights` (term "ha_noi": :724-728) boost place Hà Nội theo tag kể cả khi điểm đến là nơi khác (place tên "Bún chả Hà Nội" có tag liên quan) — rủi ro nhẹ. **Note.**
4. **`SEMANTIC_TAG_ALIASES` chứa token đơn gây false positive** (`planner.py:1046-1048`): "giá rẻ" → từ `gia` → tag ngữ nghĩa `tre_em`; "đi chùa" → `chua` → `yen_tinh` (đúng) nhưng "canh chua" cũng vậy. **Medium.**
5. **F23 nhánh `nghìn` dead** do input đã fold (`Planner.tsx:362` — pattern chứa literal có dấu, input thì mất dấu). **Low** (may mắn `nghin` sống).
6. **`VIETNAM_HOLIDAY_WINDOWS` không phải parser** (`planner.py:1055-1059`): "đi dịp tết/30-4/2-9" không bao giờ biến thành ngày; và cửa sổ Tết 20/1–20/2 là xấp xỉ cố định dù Tết âm lịch dịch theo năm. **Medium.**
7. **B20 max-places: parse xong để đó** — `planner.py:1339` lưu vào `rang_buoc` nhưng `choose_candidates:3494` không dùng giá trị này để cap. **Medium.**
8. **Frontend hỏi lại điểm đến dù backend đã hiểu**: alias BE ⊃ FE (ví dụ #4); `destinationLocation` fallback Hanoi (`Planner.tsx:13,336-339`) ghi tọa độ sai vào request — BE tự sửa nhờ `_destination_context` (:1152), nhưng `ngay_di`, `location` sai vẫn được persist vào `request`. **High.**
9. **Refine lệch chuẩn normalize** (R1-R3, `plans.py:41-51,675-683`): cùng hệ thống, input không dấu bị reject ở refine nhưng được chấp nhận ở generate. **High.**
10. **Truncation im lặng**: context 500 ký tự (`schemas.py:29`, `Planner.tsx:686`); refine `[-500:]` (`plans.py:670`) cắt **phía trước** → các ràng buộc đầu câu (budget, dislike) có thể rơi mất sau vài lượt tinh chỉnh. **Medium.**
11. **"cuối tuần" = 1 ngày** (`Planner.tsx:269`): quyết định sản phẩm được giấu trong regex keyword. **Note.**

---

## 7. Regex KHÔNG THỂ làm về nguyên tắc

1. **Relative date / calendar**: "tuần sau", "tháng 6", "thứ 7 này", "mai", "dịp lễ", "rằm", âm lịch (Tết) — cần calendar + thời điểm hiện tại + logic âm lịch, không phải chuỗi.
2. **Phạm vi phủ định**: "đừng cho tụi nhỏ đi biển", "không thích nhưng nếu rẻ thì được", "trừ hôm mưa" — cần parse cây cú pháp.
3. **Ngữ nghĩa ngân sách**: tổng vs đầu người, "rẻ", "thoải mái", "miễn phí", chuyển đổi USD/VND, "rưỡi" — vượt khuôn pattern số+đơn vị.
4. **Phân loại người**: người lớn/trẻ em/bé ("2 đứa nhỏ") — cần slot schema mới, không chỉ regex.
5. **Disambiguate địa danh**: "Bún chả Hà Nội" (tên quán) vs "Hà Nội" (điểm đến); "Nha Trang hay Đà Lạt cũng được" (cần hỏi lại, không phải first-match).
6. **Đồng nghĩa/mở vocabulary**: "xứ sương mù", "phố núi", "viên ngọc xanh", typo ("đà lặt"), slang mới — không liệt kê hết được; mỗi từ mới = sửa 3-5 chỗ (mục 5.1).
7. **Đa điểm đến liên tỉnh**: "Hà Nội → Ninh Bình → Hạ Long 5 ngày" — cần segment + routing, regex chỉ thấy 3 danh từ.
8. **Intent theo lượt hội thoại**: refine chỉ append text (`plans.py:670`) — không nhớ được "lúc nãy bảo không thích bảo tàng".
9. **Ưu tiên/trade-off**: "ưu tiên rẻ hơn là đẹp", "thà đi xa chút mà vắng" — cần so sánh ngữ nghĩa.
10. **Từ khóa đa nghĩa tiếng Việt**: "đá" (đá bóng/đá cảnh), "chua" (chùa/canh chua) — exact match bag-of-words không phân biệt được.

---

## 8. Kết luận lane 1

Lớp regex-NLU hiện tại **hữu ích nhưng không cứu được vai trò "hiểu yêu cầu tự do"**. Nó là bộ tăng tốc cho input sạch + bộ sinh câu hỏi lấp chỗ trống. Ba sự thật:

1. **Chính tả `đ` phá đúng những câu phổ biến nhất** (Đà Lạt, Đà Nẵng) ở frontend — bug 1 dòng nhưng ảnh hưởng trực diện trải nghiệm.
2. **3 chuẩn normalize ở 3 tầng** (FE giữ đ / BE fold đ / refine không fold) làm hệ thống bất nhất: cùng một câu không dấu được hiểu khác nhau ở generate vs refine.
3. **Dislike gần như trưng bày**: chỉ filter được dislike khớp term profile; dislike tự do chỉ ghi log understanding.

Nếu mục tiêu là parse tiếng Việt tự do ở mức đáng tin cậy (>80%), câu trả lời trung thực là **không — giữ nguyên trạng thì không đạt**, và chi phí vá từng pattern tăng tuyến tính theo số cách nói (mục 5.1) mà không có đường tiệm cận. Khuyến nghị chuyển cho lane 2 (LLM) phần định tính/relative/datetime, giữ regex lại cho đúng 4 việc nó giỏi: số+đơn vị đã chuẩn hóa, dd/mm range, exact city match sau khi sửa fold `đ`, và dislike-profile filter. Chi tiết thuộc lane 2-3-4.
