# Thống kê địa điểm vừa thu thập

Nguồn: `backend/data/famous_places.json` (tạo 2026-08-16 15:24:23 UTC).
File thống kê ghi lúc 2026-08-16 15:53 UTC.

Mỗi điểm được gán **hub du lịch gần nhất** (Hà Nội, Hội An, Phú Quốc…), không phải ranh giới tỉnh hành chính sau sáp nhập.

Ưu tiên: **1** = nổi tiếng (Wikipedia / di sản / curated, hoặc LLM điểm cao); **2** = nên gợi ý khi còn slot; **3** = phụ / ít nổi / OSM chưa chấm.

## Tổng quan

| Chỉ số | Số |
| --- | --- |
| Tổng địa điểm | 3.183 |
| Số tỉnh / thành (hub) | 43 |
| Ưu tiên 1 — nổi tiếng | 480 |
| Ưu tiên 2 — nên gợi ý | 218 |
| Ưu tiên 3 — phụ | 2485 |
| Hàng OSM du lịch | 3179 |
| Khớp Wikipedia (bản ghi sẵn có) | 222 |
| Khớp Wikidata (bản ghi sẵn có) | 100 |
| Wikidata thêm mới | 51 |

### Theo loại điểm

| Loại | Số |
| --- | --- |
| Danh thắng | 1278 |
| Di tích | 913 |
| Đền / chùa | 144 |
| Bảo tàng | 369 |
| Bãi biển | 123 |
| Núi | 51 |
| Hang động | 108 |
| Chợ | 13 |
| Công viên | 92 |
| Giải trí | 92 |

### Theo bằng chứng nổi tiếng

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 198 |
| Di sản / Wikidata | 80 |
| Curated | 69 |
| LLM chấm điểm | 737 |
| Quy tắc ít nổi | 436 |
| OSM chưa chấm | 1663 |

### Theo nguồn gốc bản ghi

| Nguồn | Số |
| --- | --- |
| OpenStreetMap | 3089 |
| Wikidata | 51 |
| curated | 43 |

## Theo tỉnh / thành

Sắp xếp giảm dần theo tổng điểm.

| # | Tỉnh / thành | Tổng | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 |
| --- | --- | --- | --- | --- | --- |
| 1 | Hà Nội | 429 | 73 | 14 | 342 |
| 2 | TP.HCM | 274 | 42 | 11 | 221 |
| 3 | Huế | 169 | 39 | 11 | 119 |
| 4 | Hội An | 150 | 19 | 11 | 120 |
| 5 | Vũng Tàu | 139 | 21 | 26 | 92 |
| 6 | Phú Thọ | 119 | 8 | 0 | 111 |
| 7 | Ninh Bình | 114 | 17 | 4 | 93 |
| 8 | Đà Nẵng | 112 | 25 | 22 | 65 |
| 9 | Nha Trang | 99 | 22 | 12 | 65 |
| 10 | Cần Thơ | 94 | 15 | 5 | 74 |
| 11 | Đà Lạt | 94 | 14 | 0 | 80 |
| 12 | Phú Quốc | 91 | 11 | 15 | 65 |
| 13 | Hải Phòng | 80 | 5 | 1 | 74 |
| 14 | Mỹ Tho | 78 | 5 | 2 | 71 |
| 15 | Phong Nha | 75 | 7 | 4 | 64 |
| 16 | Mũi Né | 70 | 7 | 2 | 61 |
| 17 | Sa Pa | 63 | 8 | 0 | 55 |
| 18 | Quy Nhơn | 62 | 9 | 1 | 52 |
| 19 | Tây Ninh | 60 | 7 | 1 | 52 |
| 20 | Côn Đảo | 58 | 9 | 11 | 38 |
| 21 | Đồng Hới | 51 | 6 | 8 | 37 |
| 22 | Buôn Ma Thuột | 47 | 7 | 0 | 40 |
| 23 | Đồng Văn | 47 | 0 | 0 | 47 |
| 24 | Nam Định | 45 | 8 | 2 | 35 |
| 25 | Tuy Hòa | 45 | 8 | 3 | 34 |
| 26 | Châu Đốc | 44 | 7 | 8 | 29 |
| 27 | Cao Bằng | 40 | 7 | 5 | 28 |
| 28 | Cát Bà | 37 | 8 | 7 | 22 |
| 29 | Hạ Long | 37 | 7 | 0 | 30 |
| 30 | Hà Giang | 35 | 6 | 5 | 24 |
| 31 | Vinh | 32 | 7 | 0 | 25 |
| 32 | Kon Tum | 31 | 6 | 1 | 24 |
| 33 | Mai Châu | 31 | 0 | 6 | 25 |
| 34 | Phan Rang | 28 | 7 | 5 | 16 |
| 35 | Yên Bái | 28 | 2 | 0 | 26 |
| 36 | Cà Mau | 26 | 8 | 2 | 16 |
| 37 | Thanh Hóa | 26 | 7 | 5 | 14 |
| 38 | Điện Biên Phủ | 24 | 0 | 0 | 24 |
| 39 | Cô Tô | 23 | 5 | 4 | 14 |
| 40 | Hà Tĩnh | 23 | 2 | 0 | 21 |
| 41 | Pleiku | 20 | 4 | 3 | 13 |
| 42 | Quảng Ngãi | 20 | 4 | 1 | 15 |
| 43 | Lạng Sơn | 13 | 1 | 0 | 12 |

## Chi tiết từng tỉnh / thành

Danh sách tên chỉ ghi điểm **ưu tiên 1 và 2**. Điểm ưu tiên 3 chỉ đếm, không liệt kê.

### Hà Nội

**429 điểm** — ưu tiên 1: 73; ưu tiên 2: 14; ưu tiên 3: 342.

| Loại | Số |
| --- | --- |
| Danh thắng | 151 |
| Di tích | 130 |
| Đền / chùa | 38 |
| Bảo tàng | 56 |
| Bãi biển | 1 |
| Núi | 4 |
| Hang động | 2 |
| Chợ | 2 |
| Công viên | 32 |
| Giải trí | 13 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 37 |
| Di sản / Wikidata | 9 |
| Curated | 16 |
| LLM chấm điểm | 63 |
| Quy tắc ít nổi | 72 |
| OSM chưa chấm | 232 |

**Nổi tiếng (ưu tiên 1) — 73 điểm**

- Bảo tàng Chiến thắng B52 _Bảo tàng; Di sản / Wikidata_
- Bảo tàng Công an Hà Nội _Bảo tàng; Wikipedia_
- Bảo tàng Dân tộc học Việt Nam _Bảo tàng; LLM chấm điểm_
- Bảo tàng Hoàng gia Nam Hồng _Bảo tàng; Di sản / Wikidata_
- Bảo tàng Hà Nội _Bảo tàng; Wikipedia_
- Bảo tàng Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng Lịch sử Quân sự Việt Nam _Bảo tàng; Wikipedia_
- Bảo tàng Mỹ thuật Việt Nam _Bảo tàng; Wikipedia_
- Bảo tàng Phòng không - Không quân _Bảo tàng; Wikipedia_
- Bảo tàng Phụ nữ Việt Nam _Bảo tàng; Wikipedia_
- Bảo tàng Tố Hữu _Bảo tàng; Wikipedia_
- Bảo tàng Văn học Việt Nam _Bảo tàng; LLM chấm điểm_
- Bức phù điêu chạm khắc hình tượng đức Lạc Long Quân và nhân vật về thời kỳ Hùng Vương _Di tích; Di sản / Wikidata_
- Chùa Dâu _Danh thắng; Wikipedia_
- Chùa Một Cột _Đền / chùa; Wikipedia_
- Chùa Tây Phương _Di tích; Di sản / Wikidata_
- Chùa Đào Xuyên _Di tích; Di sản / Wikidata_
- Chợ Đêm Hàng Đào – Đồng Xuân _Chợ; Curated_
- Co Loa Citadel _Danh thắng; Wikipedia_
- Công viên Hồ Tây _Giải trí; LLM chấm điểm_
- Cột đá Chùa Dạm _Di tích; Di sản / Wikidata_
- Di tích ngôi nhà số 5D phố Hàm Long _Bảo tàng; Wikipedia_
- Hàng Buồm _Danh thắng; Curated_
- Hàng Bạc _Danh thắng; Curated_
- Hàng Dầu _Danh thắng; Curated_
- Hàng Gai _Danh thắng; Curated_
- Hàng Khay _Danh thắng; Curated_
- Hàng Mã _Danh thắng; Curated_
- Hàng Ngang _Danh thắng; Curated_
- Hàng Trống _Danh thắng; Curated_
- Hàng Đào _Danh thắng; Curated_
- Hàng Đường _Danh thắng; Curated_
- Hồ Gươm _Danh thắng; Curated_
- Hồ Tây _Danh thắng; Curated_
- Khu trải nghiệm làng nghề gốm Phù Lãng _Danh thắng; LLM chấm điểm_
- Khuê Văn Các _Danh thắng; Wikipedia_
- Khỉ đuôi dài _Danh thắng; Wikipedia_
- Lunet Art Galerie _Bảo tàng; Wikipedia_
- Làng Văn hóa - Du lịch các Dân tộc Việt Nam _Giải trí; LLM chấm điểm_
- Làng giang Phù Yên _Danh thắng; LLM chấm điểm_
- Làng giấy Dương Ổ _Danh thắng; LLM chấm điểm_
- Làng gò đúc đồng Đại Bái _Danh thắng; LLM chấm điểm_
- Làng gốm Thổ Hà _Danh thắng; LLM chấm điểm_
- Làng khảm trai Bối Khê _Danh thắng; LLM chấm điểm_
- Làng khảm trai Thôn Ngọ _Danh thắng; LLM chấm điểm_
- Lăng Chủ tịch Hồ Chí Minh _Danh thắng; Curated_
- Miếu Trung Liệt _Di tích; Wikipedia_
- Nhà D67 _Danh thắng; Wikipedia_
- Nhà Hà Nhì _Danh thắng; Wikipedia_
- Nhà sàn Bác Hồ _Danh thắng; Wikipedia_
- Nhà thờ Cửa Bắc _Đền / chùa; Wikipedia_
- Nhà tù Hoả Lò _Bảo tàng; Wikipedia_
- Phố Tạ Hiện _Danh thắng; Curated_
- Phố cổ Hà Nội _Danh thắng; Curated_
- Quạ đen _Danh thắng; Wikipedia_
- Tháp Hòa Phong _Danh thắng; Wikipedia_
- Tháp nước Hàng Đậu _Danh thắng; Wikipedia_
- Tượng Alexandre Yersin _Di tích; Wikipedia_
- Tượng Phật giáo thời Tây Sơn chùa Tây Phương _Di tích; Di sản / Wikidata_
- Tượng kỷ niệm chiến thắng B52 _Danh thắng; Wikipedia_
- Tượng đài Lý Thái Tổ _Di tích; Wikipedia_
- Viện Bảo tàng Cách mạng Việt Nam _Bảo tàng; Wikipedia_
- Viện Bảo tàng Lịch sử Việt Nam _Bảo tàng; Wikipedia_
- Vườn Kiến trúc _Công viên; Wikipedia_
- Xác máy bay B52 _Danh thắng; Wikipedia_
- Đình Chèm (Đền Chèm) _Đền / chùa; Wikipedia_
- Đình Nhạn Tái _Di tích; Di sản / Wikidata_
- Đình Tam Tảo _Đền / chùa; Wikipedia_
- Đình Đọ Xá _Đền / chùa; Wikipedia_
- Đền Bạch Mã _Đền / chùa; Wikipedia_
- Đền Nội Bình Đà _Di tích; Di sản / Wikidata_
- Đền Quán Thánh _Đền / chùa; Wikipedia_
- Đền Đô _Đền / chùa; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 14 điểm**

- Blue Gallery _Bảo tàng; LLM chấm điểm_
- Bảo Tàng Hậu Cần _Bảo tàng; LLM chấm điểm_
- Bảo tàng Binh chủng Hóa học _Bảo tàng; LLM chấm điểm_
- Bảo tàng Binh chủng Thông tin liên lạc _Bảo tàng; LLM chấm điểm_
- Chùa Láng _Đền / chùa; LLM chấm điểm_
- Chùa Xã Đàn _Đền / chùa; LLM chấm điểm_
- Công viên Biển Hà Nội _Giải trí; LLM chấm điểm_
- Công viên Thủ Lệ _Giải trí; LLM chấm điểm_
- Công viên nước Royal Wave Park _Giải trí; LLM chấm điểm_
- Kid's House on the tree _Danh thắng; LLM chấm điểm_
- Lotte World Aquarium _Giải trí; LLM chấm điểm_
- Lệ Mật Snake Kingdom _Giải trí; LLM chấm điểm_
- Thiên đường Bảo Sơn _Giải trí; LLM chấm điểm_
- đền Đại Lộ _Danh thắng; LLM chấm điểm_

### TP.HCM

**274 điểm** — ưu tiên 1: 42; ưu tiên 2: 11; ưu tiên 3: 221.

| Loại | Số |
| --- | --- |
| Danh thắng | 70 |
| Di tích | 78 |
| Đền / chùa | 40 |
| Bảo tàng | 50 |
| Núi | 4 |
| Hang động | 8 |
| Chợ | 2 |
| Công viên | 9 |
| Giải trí | 13 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 30 |
| Di sản / Wikidata | 5 |
| Curated | 5 |
| LLM chấm điểm | 42 |
| Quy tắc ít nổi | 50 |
| OSM chưa chấm | 142 |

**Nổi tiếng (ưu tiên 1) — 42 điểm**

- Annam Gallery _Bảo tàng; Wikipedia_
- Bảo Tàng Địa Chất _Bảo tàng; Wikipedia_
- Bảo tàng Chứng tích Chiến tranh _Bảo tàng; Curated_
- Bảo tàng Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng Không quân phía Nam _Bảo tàng; Di sản / Wikidata_
- Bảo tàng Lịch sử Thành phố Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng Lực lượng Vũ trang miền Đông Nam Bộ _Bảo tàng; Wikipedia_
- Bảo tàng Mỹ thuật Thành phố Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng Phụ nữ Nam Bộ _Bảo tàng; Wikipedia_
- Bảo tàng Thành phố Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng Thành phố Đồng Nai _Bảo tàng; Wikipedia_
- Bảo tàng tỉnh Bình Dương _Bảo tàng; Di sản / Wikidata_
- Chùa Giác Lâm _Đền / chùa; Wikipedia_
- Chùa Giác Viên _Đền / chùa; Wikipedia_
- Chùa Phước Hải _Đền / chùa; Wikipedia_
- Chợ Bến Thành _Chợ; Curated_
- Công viên Văn hóa Đầm Sen _Giải trí; Wikipedia_
- Công viên giải trí VinWonders Grand Park _Giải trí; LLM chấm điểm_
- Di tích Lịch sử Văn hóa mộ Phan Châu Trinh _Di tích; Wikipedia_
- Dinh Độc Lập _Danh thắng; Curated_
- Hội quán Lệ Châu _Đền / chùa; Wikipedia_
- Hội quán Nghĩa Nhuận _Đền / chùa; Wikipedia_
- Hội quán Phước An _Đền / chùa; Wikipedia_
- Hội quán Quỳnh Phủ _Đền / chùa; Wikipedia_
- Khu du lịch Suối Tiên _Giải trí; Wikipedia_
- Lăng Trương Vĩnh Ký _Di tích; Wikipedia_
- Nhà hát Thành phố _Danh thắng; LLM chấm điểm_
- Nhà thờ Thánh Jeanne d'Arc _Đền / chùa; Wikipedia_
- Nhà thờ Đức Bà _Di tích; Curated_
- Nhà thờ Đức Bà Sài Gòn _Đền / chùa; Wikipedia_
- Phố đi bộ Nguyễn Huệ _Danh thắng; Curated_
- Quang San Art Museum _Bảo tàng; Di sản / Wikidata_
- Tượng đài Công Nông Binh _Di tích; Wikipedia_
- Vườn quốc gia Cát Tiên _Di tích; Di sản / Wikidata_
- Vườn quốc gia Cát Tiên _Danh thắng; Di sản / Wikidata_
- Đình Bình Hòa _Đền / chùa; Wikipedia_
- Đình Bình Đông _Đền / chùa; Wikipedia_
- Đình Chí Hòa _Đền / chùa; Wikipedia_
- Đình Minh Hương Gia Thạnh _Đền / chùa; Wikipedia_
- Đình Thông Tây Hội _Đền / chùa; Wikipedia_
- Đình Tân Kiểng _Đền / chùa; Wikipedia_
- Đền thờ Vua Hùng _Đền / chùa; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 11 điểm**

- Biệt thự Nguyễn Văn Hảo _Danh thắng; LLM chấm điểm_
- Bưu điện Trung tâm Sài Gòn _Danh thắng; LLM chấm điểm_
- Cu Chi Wildlife Rescue Station _Danh thắng; LLM chấm điểm_
- Công Viên Ven Sông An Phú Hưng _Danh thắng; LLM chấm điểm_
- Công viên Nước Đầm Sen _Giải trí; LLM chấm điểm_
- Công viên bờ sông Sài Gòn _Danh thắng; LLM chấm điểm_
- Công viên nước Grand Park _Giải trí; LLM chấm điểm_
- Cầu Mống _Danh thắng; LLM chấm điểm_
- Hải Dương Water Park _Giải trí; LLM chấm điểm_
- The Commons Thu Thiem _Danh thắng; LLM chấm điểm_
- Vườn thú Mỹ Quỳnh _Giải trí; LLM chấm điểm_

### Huế

**169 điểm** — ưu tiên 1: 39; ưu tiên 2: 11; ưu tiên 3: 119.

| Loại | Số |
| --- | --- |
| Danh thắng | 70 |
| Di tích | 67 |
| Đền / chùa | 6 |
| Bảo tàng | 21 |
| Bãi biển | 1 |
| Núi | 1 |
| Hang động | 2 |
| Chợ | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 19 |
| Di sản / Wikidata | 7 |
| Curated | 4 |
| LLM chấm điểm | 42 |
| Quy tắc ít nổi | 21 |
| OSM chưa chấm | 76 |

**Nổi tiếng (ưu tiên 1) — 39 điểm**

- Bach Ma National Park _Danh thắng; LLM chấm điểm_
- Blue car _Danh thắng; Wikipedia_
- Boi Lang _Danh thắng; Wikipedia_
- Bảo tàng Cổ vật Cung đình Huế _Bảo tàng; Wikipedia_
- Bảo tàng Hồ Chí Minh _Bảo tàng; Wikipedia_
- Chùa Báo Quốc _Danh thắng; Wikipedia_
- Chùa Thiên Mụ _Đền / chùa; Curated_
- Chương Đức _Di tích; Wikipedia_
- Cung Diên Thọ _Danh thắng; LLM chấm điểm_
- Cung Trường Sanh _Danh thắng; LLM chấm điểm_
- Duyệt Thị Đường _Danh thắng; LLM chấm điểm_
- Holy Cannons of the Citadel of Hue _Danh thắng; LLM chấm điểm_
- Hòn Chén Temple _Di tích; Di sản / Wikidata_
- Hổ Quyền _Di tích; Di sản / Wikidata_
- Khai Dinh _Đền / chùa; Wikipedia_
- Khu Dự trữ thiên nhiên Phong Điền _Danh thắng; LLM chấm điểm_
- Khu bảo tồn Sao la Huế _Danh thắng; LLM chấm điểm_
- Không gian Văn hóa Lục Bộ _Danh thắng; Di sản / Wikidata_
- Lăng Dục Đức _Di tích; Wikipedia_
- Lăng Gia Long _Di tích; Wikipedia_
- Lăng Khải Định _Di tích; Curated_
- Lăng Minh Mạng _Di tích; Wikipedia_
- Lăng Thiệu Trị _Di tích; Wikipedia_
- Lăng Tự Đức _Di tích; Wikipedia_
- Lăng Đồng Khánh _Di tích; Wikipedia_
- Quoc Tu Dieu De _Đền / chùa; Wikipedia_
- Quốc Tử Giám _Danh thắng; LLM chấm điểm_
- Sông Hương _Danh thắng; Curated_
- Thanh Toan Bridge _Danh thắng; LLM chấm điểm_
- Tháp chuông _Di tích; Wikipedia_
- Thích Quảng Đức xe _Danh thắng; Wikipedia_
- Trấn Hải Thành _Di tích; Di sản / Wikidata_
- Tử Cấm Thành _Danh thắng; Wikipedia_
- Vườn quốc gia Bạch Mã _Danh thắng; Di sản / Wikidata_
- illegal entrance to palace, climb over _Danh thắng; Wikipedia_
- Điện Thái Hòa _Danh thắng; Di sản / Wikidata_
- Đàn Nam Giao (triều Nguyễn) _Di tích; Di sản / Wikidata_
- Đại Nội Huế _Di tích; Curated_
- ĐỊA ĐIÊM MẠI TÁNG BÀ HOÀNG THỊ LOAN (1868- 1901) _Di tích; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 11 điểm**

- Cầu ngói Thanh Toàn _Danh thắng; LLM chấm điểm_
- Ho Thuy Tien _Danh thắng; LLM chấm điểm_
- Hồ Sơn Thọ _Danh thắng; LLM chấm điểm_
- Khu bảo tồn thiên nhiên Đakrông _Danh thắng; LLM chấm điểm_
- Khu bảo tồn thiên nhiên Đakrông _Danh thắng; LLM chấm điểm_
- Làng cổ Phước Tích _Danh thắng; LLM chấm điểm_
- Quoc Hoc _Danh thắng; LLM chấm điểm_
- Stele Pavilion _Danh thắng; LLM chấm điểm_
- Trường An Môn _Danh thắng; LLM chấm điểm_
- Tượng đài Quan Thế Âm Bồ Tát _Danh thắng; LLM chấm điểm_
- Đông Khuyết Đài _Danh thắng; LLM chấm điểm_

### Hội An

**150 điểm** — ưu tiên 1: 19; ưu tiên 2: 11; ưu tiên 3: 120.

| Loại | Số |
| --- | --- |
| Danh thắng | 40 |
| Di tích | 75 |
| Đền / chùa | 2 |
| Bảo tàng | 22 |
| Bãi biển | 6 |
| Chợ | 2 |
| Giải trí | 3 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 7 |
| Di sản / Wikidata | 3 |
| Curated | 2 |
| LLM chấm điểm | 27 |
| Quy tắc ít nổi | 11 |
| OSM chưa chấm | 100 |

**Nổi tiếng (ưu tiên 1) — 19 điểm**

- A6 _Di tích; Di sản / Wikidata_
- Bai Bien Ha Binh _Bãi biển; LLM chấm điểm_
- Bai Bien Tan An _Bãi biển; LLM chấm điểm_
- Bãi Bìm _Bãi biển; LLM chấm điểm_
- Bãi biển Bình Minh _Bãi biển; LLM chấm điểm_
- Bãi Ông _Bãi biển; LLM chấm điểm_
- Bảo Tàng Thó Sản _Bảo tàng; Wikipedia_
- Bảo tàng Đà Nẵng (cơ sở 2) _Bảo tàng; Di sản / Wikidata_
- Chùa Cầu _Danh thắng; Curated_
- D2 _Di tích; Wikipedia_
- DI TÍCH ĐỈNH HỘI AN _Danh thắng; Wikipedia_
- Di San Vô Giá _Bảo tàng; Wikipedia_
- Hội quán Triều Châu _Danh thắng; Wikipedia_
- Phan Kim Chi Art Gallery _Bảo tàng; Wikipedia_
- Phố cổ Hội An _Danh thắng; Curated_
- Sa Huynh _Bảo tàng; Wikipedia_
- Tan Ky _Bảo tàng; Di sản / Wikidata_
- Vanessa Beach _Bãi biển; LLM chấm điểm_
- VinWonders Nam Hội An _Giải trí; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 11 điểm**

- Boa tang gom su mau dich _Bảo tàng; LLM chấm điểm_
- Bảo tàng Hội An _Bảo tàng; LLM chấm điểm_
- Bảo tàng Quân đội tỉnh Quảng Nam _Bảo tàng; LLM chấm điểm_
- Bảo tàng Điện Bàn _Bảo tàng; LLM chấm điểm_
- Diep Dong Nguyen _Bảo tàng; LLM chấm điểm_
- Hoi An Memories Land _Giải trí; LLM chấm điểm_
- Hoi An Museum of Traditional Medicine _Bảo tàng; LLM chấm điểm_
- My Son Museum _Bảo tàng; LLM chấm điểm_
- Nhà cổ Phùng Hưng _Bảo tàng; LLM chấm điểm_
- Nhà cổ Quân Thắng _Bảo tàng; LLM chấm điểm_
- Nhà cổ Đức An _Bảo tàng; LLM chấm điểm_

### Vũng Tàu

**139 điểm** — ưu tiên 1: 21; ưu tiên 2: 26; ưu tiên 3: 92.

| Loại | Số |
| --- | --- |
| Danh thắng | 36 |
| Di tích | 45 |
| Đền / chùa | 16 |
| Bảo tàng | 11 |
| Bãi biển | 22 |
| Núi | 3 |
| Hang động | 1 |
| Công viên | 1 |
| Giải trí | 4 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 4 |
| Curated | 2 |
| LLM chấm điểm | 67 |
| Quy tắc ít nổi | 36 |
| OSM chưa chấm | 30 |

**Nổi tiếng (ưu tiên 1) — 21 điểm**

- 5 Hiếu _Bãi biển; LLM chấm điểm_
- Bãi Dâu _Bãi biển; LLM chấm điểm_
- Bãi Sau _Bãi biển; Curated_
- Bãi Trước _Bãi biển; LLM chấm điểm_
- Bãi tắm Thủy Tiên _Bãi biển; LLM chấm điểm_
- Bãi tắm Trân Châu _Bãi biển; LLM chấm điểm_
- Bãi tắm Đèo Nước Ngọt _Bãi biển; LLM chấm điểm_
- Bãi Ô Quắn _Bãi biển; LLM chấm điểm_
- Bạch Dinh _Danh thắng; LLM chấm điểm_
- Công viên Bãi Trước _Danh thắng; Wikipedia_
- Dinh Cô _Đền / chùa; LLM chấm điểm_
- Hồ Mây Park _Giải trí; LLM chấm điểm_
- Hồ Tràm Complex _Danh thắng; LLM chấm điểm_
- Khu bảo tồn thiên nhiên Bình Châu - Phước Bửu _Danh thắng; LLM chấm điểm_
- Nhà anh Lê Thành Duy _Bảo tàng; Wikipedia_
- Nhà thờ Vũng Tàu _Đền / chùa; LLM chấm điểm_
- Phước Hải _Bãi biển; LLM chấm điểm_
- Tượng Chúa Kitô Vua _Danh thắng; Wikipedia_
- Tượng Chúa Kitô Vũng Tàu _Danh thắng; Curated_
- Đồi Con Heo _Danh thắng; Wikipedia_
- Động Huỳnh Hổ _Hang động; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 26 điểm**

- Bãi Dứa _Bãi biển; LLM chấm điểm_
- Bãi Lãng Du _Bãi biển; LLM chấm điểm_
- Bãi Vọng Nguyệt _Bãi biển; LLM chấm điểm_
- Bãi tắm Long Hải _Bãi biển; LLM chấm điểm_
- Bảo tàng Bà Rịa-Vũng Tàu _Bảo tàng; LLM chấm điểm_
- Bảo tàng Vũ khí cổ Robert Taylor _Bảo tàng; LLM chấm điểm_
- Bảo tàng địa đạo Long Phước _Bảo tàng; LLM chấm điểm_
- Cáp treo Vũng Tàu _Danh thắng; LLM chấm điểm_
- Công viên Thỏ Trắng _Giải trí; LLM chấm điểm_
- Công viên nước Vũng Tàu _Giải trí; LLM chấm điểm_
- Di tích Minh Đạm _Danh thắng; LLM chấm điểm_
- Di tích nhà má Tám Nhung _Bảo tàng; LLM chấm điểm_
- Ho Coc Beach resort _Bãi biển; LLM chấm điểm_
- Khu du lịch Đèo Nước Ngọt _Danh thắng; LLM chấm điểm_
- Minera Hot Springs Bình Châu _Danh thắng; LLM chấm điểm_
- Monkey Island _Danh thắng; LLM chấm điểm_
- Nhà Lớn Long Sơn _Bảo tàng; LLM chấm điểm_
- Nhà lưu niệm Võ Thị Sáu _Bảo tàng; LLM chấm điểm_
- Niết Bàn Tịnh Xá _Đền / chùa; LLM chấm điểm_
- Palace Long Hai Resort _Bãi biển; LLM chấm điểm_
- Phòng trưng bày Di tích Núi Dinh _Bảo tàng; LLM chấm điểm_
- Thiền viện Linh Chiếu _Đền / chùa; LLM chấm điểm_
- Thiền viện Thường Chiếu _Đền / chùa; LLM chấm điểm_
- Thích ca Phật Đài _Đền / chùa; LLM chấm điểm_
- Tropicana Park _Giải trí; LLM chấm điểm_
- Đảo Khỉ _Danh thắng; LLM chấm điểm_

### Phú Thọ

**119 điểm** — ưu tiên 1: 8; ưu tiên 2: 0; ưu tiên 3: 111.

| Loại | Số |
| --- | --- |
| Danh thắng | 17 |
| Di tích | 82 |
| Đền / chùa | 1 |
| Bảo tàng | 8 |
| Núi | 2 |
| Hang động | 3 |
| Công viên | 3 |
| Giải trí | 3 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 3 |
| Di sản / Wikidata | 4 |
| Curated | 1 |
| Quy tắc ít nổi | 12 |
| OSM chưa chấm | 99 |

**Nổi tiếng (ưu tiên 1) — 8 điểm**

- Bảo tàng Hùng Vương _Bảo tàng; Wikipedia_
- Bảo tàng Hùng Vương _Bảo tàng; Wikipedia_
- Cầu Vàng _Danh thắng; Curated_
- Phế tích Pháp _Di tích; Wikipedia_
- Vườn quốc gia Tam Đảo _Công viên; Di sản / Wikidata_
- Vườn quốc gia Tam Đảo _Danh thắng; Di sản / Wikidata_
- Vườn quốc gia Xuân Sơn _Công viên; Di sản / Wikidata_
- Vườn quốc gia Xuân Sơn _Danh thắng; Di sản / Wikidata_

### Ninh Bình

**114 điểm** — ưu tiên 1: 17; ưu tiên 2: 4; ưu tiên 3: 93.

| Loại | Số |
| --- | --- |
| Danh thắng | 63 |
| Di tích | 13 |
| Đền / chùa | 12 |
| Bảo tàng | 6 |
| Núi | 1 |
| Hang động | 15 |
| Chợ | 1 |
| Công viên | 2 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 7 |
| Di sản / Wikidata | 1 |
| Curated | 4 |
| LLM chấm điểm | 23 |
| Quy tắc ít nổi | 6 |
| OSM chưa chấm | 73 |

**Nổi tiếng (ưu tiên 1) — 17 điểm**

- Chùa Bái Đính cổ _Danh thắng; LLM chấm điểm_
- Chùa Nhất Trụ _Đền / chùa; Wikipedia_
- Cố đô Hoa Lư _Danh thắng; Curated_
- Dong am tiem. _Danh thắng; Wikipedia_
- Dộng Thiên Cung _Hang động; Wikipedia_
- Hang Con Moong _Di tích; Di sản / Wikidata_
- Hang Lâm _Hang động; Wikipedia_
- Hang Múa _Danh thắng; Curated_
- Khu bảo tồn thiên nhiên đất ngập nước Vân Long _Danh thắng; LLM chấm điểm_
- Khu du lịch sinh thái Tràng An _Danh thắng; LLM chấm điểm_
- Lang Cu Sau _Di tích; Wikipedia_
- Tam Cốc _Bảo tàng; Curated_
- Tháp Báo Thiên _Danh thắng; Wikipedia_
- Tien Grotto _Hang động; LLM chấm điểm_
- Tràng An _Danh thắng; Curated_
- Vườn quốc gia Cúc Phương _Danh thắng; Wikipedia_
- Động Hương Tích _Hang động; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 4 điểm**

- Cây Đăng Cổ Thụ _Danh thắng; LLM chấm điểm_
- Cổng Tam Quan _Danh thắng; LLM chấm điểm_
- Làng gốm Bồ Bát _Danh thắng; LLM chấm điểm_
- Làng gốm Gia Thủy _Danh thắng; LLM chấm điểm_

### Đà Nẵng

**112 điểm** — ưu tiên 1: 25; ưu tiên 2: 22; ưu tiên 3: 65.

| Loại | Số |
| --- | --- |
| Danh thắng | 48 |
| Di tích | 11 |
| Đền / chùa | 8 |
| Bảo tàng | 11 |
| Bãi biển | 14 |
| Núi | 1 |
| Hang động | 5 |
| Chợ | 1 |
| Công viên | 4 |
| Giải trí | 9 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 5 |
| Di sản / Wikidata | 2 |
| Curated | 7 |
| LLM chấm điểm | 73 |
| Quy tắc ít nổi | 5 |
| OSM chưa chấm | 20 |

**Nổi tiếng (ưu tiên 1) — 25 điểm**

- Bà Nà Hills _Giải trí; Curated_
- Bãi Biển Sơn Trà _Bãi biển; LLM chấm điểm_
- Bãi biển Mỹ Khê _Bãi biển; Curated_
- Bãi tắm Non Nước _Bãi biển; LLM chấm điểm_
- Bảo tàng Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng _Bảo tàng; Wikipedia_
- Bảo tàng Quân khu 5 _Bảo tàng; Wikipedia_
- Bảo tàng Điêu khắc Chăm _Bảo tàng; Curated_
- Chùa Linh Ứng Sơn Trà _Đền / chùa; Curated_
- Cầu Rồng _Danh thắng; Curated_
- Cầu Sông Hàn _Danh thắng; LLM chấm điểm_
- Cầu Vàng _Danh thắng; Curated_
- Dong Giang Gate of Heaven Eco-tourism Area _Danh thắng; LLM chấm điểm_
- Dragon's Tail _Danh thắng; Wikipedia_
- Hải Vân Quan _Danh thắng; LLM chấm điểm_
- Khu bảo tồn thiên nhiên Sông Thanh _Công viên; Di sản / Wikidata_
- Lăng Cô _Bãi biển; LLM chấm điểm_
- My An Beach _Bãi biển; LLM chấm điểm_
- Ngũ Hành Sơn _Danh thắng; Curated_
- Non Nuoc Beach _Danh thắng; LLM chấm điểm_
- Sun World Bà Nà Hills _Giải trí; LLM chấm điểm_
- Thành Điện Hải _Di tích; Wikipedia_
- Vườn quốc gia Bạch Mã _Công viên; Di sản / Wikidata_
- Đèo Hải Vân _Danh thắng; LLM chấm điểm_
- Động Âm Phủ _Hang động; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 22 điểm**

- Art in Paradise Da Nang 3D Museum _Bảo tàng; LLM chấm điểm_
- Bho hoong village ethnique _Danh thắng; LLM chấm điểm_
- Bãi Bà Đa _Bãi biển; LLM chấm điểm_
- Bãi Cát Vàng _Bãi biển; LLM chấm điểm_
- Bãi biển Bắc _Bãi biển; LLM chấm điểm_
- Bãi biển Tiên Sa _Bãi biển; LLM chấm điểm_
- Bảo tàng Đà Nẵng _Bảo tàng; LLM chấm điểm_
- Chợ Cồn _Chợ; LLM chấm điểm_
- Chợ đêm Helio _Danh thắng; LLM chấm điểm_
- Cầu Thuận Phước _Danh thắng; LLM chấm điểm_
- Cầu Tiên Sơn _Danh thắng; LLM chấm điểm_
- Cầu Trần Thị Lý _Danh thắng; LLM chấm điểm_
- Fantasy Park _Giải trí; LLM chấm điểm_
- Huyen Khong Cave _Hang động; LLM chấm điểm_
- Khu Du Lịch Sinh Thái Suối Lương _Danh thắng; LLM chấm điểm_
- Làng đá mỹ nghệ Non Nước _Danh thắng; LLM chấm điểm_
- Rừng đặc dụng Bà Nà - Núi Chúa _Danh thắng; LLM chấm điểm_
- Rừng đặc dụng Sơn Trà _Danh thắng; LLM chấm điểm_
- Thuỷ Sơn _Danh thắng; LLM chấm điểm_
- Thác Nhị Hồ _Giải trí; LLM chấm điểm_
- Trung tâm Giải trí Phức hợp Helio Center _Giải trí; LLM chấm điểm_
- Waterpark 365 Mikazuki Hotel _Giải trí; LLM chấm điểm_

### Nha Trang

**99 điểm** — ưu tiên 1: 22; ưu tiên 2: 12; ưu tiên 3: 65.

| Loại | Số |
| --- | --- |
| Danh thắng | 27 |
| Di tích | 28 |
| Đền / chùa | 2 |
| Bảo tàng | 9 |
| Bãi biển | 10 |
| Núi | 7 |
| Hang động | 6 |
| Công viên | 1 |
| Giải trí | 9 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 3 |
| Curated | 14 |
| LLM chấm điểm | 41 |
| Quy tắc ít nổi | 21 |
| OSM chưa chấm | 20 |

**Nổi tiếng (ưu tiên 1) — 22 điểm**

- An Viên Beach _Bãi biển; LLM chấm điểm_
- Bào Tàng Alexandre Yersin _Bảo tàng; Wikipedia_
- Bãi Dài _Bãi biển; LLM chấm điểm_
- Bãi Dài Cam Ranh _Bãi biển; Curated_
- Bãi biển Nha Trang _Bãi biển; Curated_
- Bảo tàng Hải dương học Nha Trang _Bảo tàng; LLM chấm điểm_
- Chùa Long Sơn _Đền / chùa; Curated_
- Hòn Chồng _Bảo tàng; Curated_
- Hòn Mun _Danh thắng; Curated_
- Hòn Tre _Núi; Curated_
- Hòn Tằm _Danh thắng; Curated_
- I-Resort Nha Trang _Giải trí; Curated_
- Long Thanh Art Gallery _Bảo tàng; Wikipedia_
- Lầu Bảo Đại _Danh thắng; LLM chấm điểm_
- Nhà thờ Đá Nha Trang _Đền / chùa; Curated_
- Tháp Bà Ponagar _Di tích; Curated_
- Tháp Po Nagar _Di tích; Wikipedia_
- VinPearl _Giải trí; LLM chấm điểm_
- VinWonders Nha Trang _Giải trí; Curated_
- Viện Hải dương học Nha Trang _Bảo tàng; Curated_
- Vịnh Nha Trang _Danh thắng; Curated_
- Đảo Khỉ Nha Trang _Danh thắng; Curated_

**Nên gợi ý (ưu tiên 2) — 12 điểm**

- 100 Eggs Mud Bath _Giải trí; LLM chấm điểm_
- Bán Đảo Hòn Gốm _Danh thắng; LLM chấm điểm_
- Bãi Rạng - Hòn Ghềnh _Danh thắng; LLM chấm điểm_
- Bãi Tắm Hòn Chồng _Bãi biển; LLM chấm điểm_
- Bãi biển Dốc Lết _Bãi biển; LLM chấm điểm_
- Bãi tắm MIA _Bãi biển; LLM chấm điểm_
- Khu bảo tồn thiên nhiên Hòn Bà _Danh thắng; LLM chấm điểm_
- Khu du lịch Thác Yang Bay _Danh thắng; LLM chấm điểm_
- Mai Loc Photo Gallery _Bảo tàng; LLM chấm điểm_
- Splash Bay _Giải trí; LLM chấm điểm_
- Underwater world _Giải trí; LLM chấm điểm_
- Đảo Khỉ _Danh thắng; LLM chấm điểm_

### Cần Thơ

**94 điểm** — ưu tiên 1: 15; ưu tiên 2: 5; ưu tiên 3: 74.

| Loại | Số |
| --- | --- |
| Danh thắng | 39 |
| Di tích | 26 |
| Đền / chùa | 5 |
| Bảo tàng | 11 |
| Bãi biển | 1 |
| Chợ | 2 |
| Công viên | 6 |
| Giải trí | 4 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 8 |
| Di sản / Wikidata | 1 |
| Curated | 1 |
| LLM chấm điểm | 12 |
| Quy tắc ít nổi | 13 |
| OSM chưa chấm | 59 |

**Nổi tiếng (ưu tiên 1) — 15 điểm**

- Bảo tàng Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng thành phố Cần Thơ _Bảo tàng; Wikipedia_
- Bảo tàng tỉnh Kiên Giang _Bảo tàng; Wikipedia_
- Bảo tàng Đồng Tháp _Bảo tàng; Di sản / Wikidata_
- Chùa Mahatup វត្ត​សេរី​តេ​ជោ​មហា​ទប់ _Đền / chùa; Wikipedia_
- Chợ nổi Cái Răng _Chợ; Curated_
- Công Viên Lưu Hữu Phước _Giải trí; Wikipedia_
- Floating Market tourist _Danh thắng; LLM chấm điểm_
- Hồ nước ngọt _Danh thắng; Wikipedia_
- Khu Du Lịch Vinh Sang _Danh thắng; LLM chấm điểm_
- Mộ ông Huyện Bình _Di tích; Wikipedia_
- Người tình nhà cổ Bình Thủy _Danh thắng; LLM chấm điểm_
- Nhà cổ Cai Cường _Danh thắng; LLM chấm điểm_
- Nhà cổ Huỳnh Thủy Lê _Danh thắng; Wikipedia_
- Phong Điền Floating Market _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 5 điểm**

- Du lịch Sinh thái Mỏ Ó _Danh thắng; LLM chấm điểm_
- Flower market _Danh thắng; LLM chấm điểm_
- Khu bảo tồn thiên nhiên Lung Ngọc Hoàng _Danh thắng; LLM chấm điểm_
- Orchard with fruit tasting _Danh thắng; LLM chấm điểm_
- Orchard with fruit tasting _Danh thắng; LLM chấm điểm_

### Đà Lạt

**94 điểm** — ưu tiên 1: 14; ưu tiên 2: 0; ưu tiên 3: 80.

| Loại | Số |
| --- | --- |
| Danh thắng | 55 |
| Di tích | 15 |
| Bảo tàng | 15 |
| Núi | 4 |
| Công viên | 4 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 6 |
| Di sản / Wikidata | 4 |
| Curated | 4 |
| Quy tắc ít nổi | 6 |
| OSM chưa chấm | 74 |

**Nổi tiếng (ưu tiên 1) — 14 điểm**

- 3D World _Bảo tàng; Wikipedia_
- Biệt thự Hằng Nga _Danh thắng; Curated_
- Ga Đà Lạt _Danh thắng; Wikipedia_
- Hồ Xuân Hương _Danh thắng; Curated_
- Khu bảo tồn thiên nhiên Tà Đung _Công viên; Di sản / Wikidata_
- Nhà thờ Con Gà _Di tích; Curated_
- Thung Lũng Tình Yêu _Danh thắng; Curated_
- Vườn dâu Công nghệ cao Bình Yên _Danh thắng; Wikipedia_
- Vườn hoa Ánh Sáng _Công viên; Wikipedia_
- Vườn quốc gia Bidoup Núi Bà _Công viên; Di sản / Wikidata_
- Vườn quốc gia Bidoup Núi Bà _Danh thắng; Di sản / Wikidata_
- Vườn quốc gia Chư Yang Sin _Danh thắng; Di sản / Wikidata_
- Vườn quốc gia Phước Bình _Danh thắng; Wikipedia_
- nhà thờ Camly _Danh thắng; Wikipedia_

### Phú Quốc

**91 điểm** — ưu tiên 1: 11; ưu tiên 2: 15; ưu tiên 3: 65.

| Loại | Số |
| --- | --- |
| Danh thắng | 32 |
| Di tích | 26 |
| Đền / chùa | 1 |
| Bảo tàng | 9 |
| Bãi biển | 14 |
| Núi | 4 |
| Hang động | 1 |
| Giải trí | 4 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 2 |
| Curated | 2 |
| LLM chấm điểm | 48 |
| Quy tắc ít nổi | 16 |
| OSM chưa chấm | 23 |

**Nổi tiếng (ưu tiên 1) — 11 điểm**

- Bai Dai Beach _Bãi biển; LLM chấm điểm_
- Bãi Dài _Bãi biển; LLM chấm điểm_
- Bãi Sao _Bãi biển; Curated_
- Bãi Trường _Danh thắng; LLM chấm điểm_
- Bãi Trường Beach _Danh thắng; LLM chấm điểm_
- Dinh Cậu _Danh thắng; Curated_
- VinWonders Phú Quốc _Giải trí; LLM chấm điểm_
- Vinpearl Safari _Giải trí; LLM chấm điểm_
- Vườn quốc gia Phú Quốc _Danh thắng; Wikipedia_
- Vịnh Emerald _Danh thắng; Wikipedia_
- Đá Dựng _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 15 điểm**

- Bao Tang Phu Quoc _Bảo tàng; LLM chấm điểm_
- Bãi Gành Dầu _Bãi biển; LLM chấm điểm_
- Bãi Khem _Bãi biển; LLM chấm điểm_
- Bãi Ông Lang _Bãi biển; LLM chấm điểm_
- Bảo tàng Gấu Teddy (Teddy Bear Museum) _Bảo tàng; LLM chấm điểm_
- Công viên nước Aquatopia _Giải trí; LLM chấm điểm_
- Di Tích Lịch Sử - Nhà Tù Phú Quốc _Bảo tàng; LLM chấm điểm_
- Fausse plage starfish _Danh thắng; LLM chấm điểm_
- Hang Cá Sấu _Danh thắng; LLM chấm điểm_
- Núi Đèn _Danh thắng; LLM chấm điểm_
- Start of hike trail to Tiên Sơn Đỉnh summit _Danh thắng; LLM chấm điểm_
- THE PEAK _Danh thắng; LLM chấm điểm_
- Tháp 7 tầng _Bảo tàng; LLM chấm điểm_
- Trúc Lâm Hộ Quốc Zen Monastery _Đền / chùa; LLM chấm điểm_
- Điểm Tạp Trung Tham Quan Vườn quốc gia Phú Quốc _Danh thắng; LLM chấm điểm_

### Hải Phòng

**80 điểm** — ưu tiên 1: 5; ưu tiên 2: 1; ưu tiên 3: 74.

| Loại | Số |
| --- | --- |
| Danh thắng | 28 |
| Di tích | 29 |
| Bảo tàng | 11 |
| Bãi biển | 1 |
| Núi | 4 |
| Hang động | 1 |
| Công viên | 3 |
| Giải trí | 3 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 2 |
| Di sản / Wikidata | 3 |
| LLM chấm điểm | 26 |
| Quy tắc ít nổi | 17 |
| OSM chưa chấm | 32 |

**Nổi tiếng (ưu tiên 1) — 5 điểm**

- Bảo tàng Hải Phòng _Bảo tàng; Wikipedia_
- Bảo tàng tỉnh Hải Dương _Bảo tàng; Di sản / Wikidata_
- Chùa Khám Lạng _Di tích; Di sản / Wikidata_
- Khu di tích Côn Sơn - Kiếp Bạc _Danh thắng; Wikipedia_
- Quần thể di tích danh thắng Yên Tử _Di tích; Di sản / Wikidata_

**Nên gợi ý (ưu tiên 2) — 1 điểm**

- VinWonders Vũ Yên _Giải trí; LLM chấm điểm_

### Mỹ Tho

**78 điểm** — ưu tiên 1: 5; ưu tiên 2: 2; ưu tiên 3: 71.

| Loại | Số |
| --- | --- |
| Danh thắng | 23 |
| Di tích | 32 |
| Bảo tàng | 17 |
| Công viên | 3 |
| Giải trí | 3 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| Di sản / Wikidata | 3 |
| LLM chấm điểm | 12 |
| Quy tắc ít nổi | 20 |
| OSM chưa chấm | 42 |

**Nổi tiếng (ưu tiên 1) — 5 điểm**

- Bảo tàng Tiền Giang _Bảo tàng; Wikipedia_
- Bảo tàng tỉnh Long An _Bảo tàng; Di sản / Wikidata_
- Bộ sưu tập hiện vật vàng tại Long An _Di tích; Di sản / Wikidata_
- Mê Kông _Di tích; Di sản / Wikidata_
- nhà cổ bên kia cầu _Bảo tàng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 2 điểm**

- Bảo tàng tỉnh _Bảo tàng; LLM chấm điểm_
- bảo tàng Gò Thành _Bảo tàng; LLM chấm điểm_

### Phong Nha

**75 điểm** — ưu tiên 1: 7; ưu tiên 2: 4; ưu tiên 3: 64.

| Loại | Số |
| --- | --- |
| Danh thắng | 38 |
| Di tích | 12 |
| Hang động | 21 |
| Công viên | 1 |
| Giải trí | 3 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 4 |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 13 |
| Quy tắc ít nổi | 11 |
| OSM chưa chấm | 45 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Hang 8 cô _Danh thắng; LLM chấm điểm_
- Hang Sơn Đoòng _Hang động; Wikipedia_
- Hang Én _Hang động; Wikipedia_
- Khu Du Lich Dong Phong Nha Ke Bang _Danh thắng; Wikipedia_
- Vườn quốc gia Phong Nha - Kẻ Bàng _Di tích; Di sản / Wikidata_
- Vườn quốc gia Phong Nha - Kẻ Bàng _Danh thắng; Di sản / Wikidata_
- Động Thiên Đường _Hang động; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 4 điểm**

- Hang Ken Dry _Danh thắng; LLM chấm điểm_
- Hang Ken Wet _Danh thắng; LLM chấm điểm_
- Hang Sun Oxalis _Danh thắng; LLM chấm điểm_
- Động Tiên Sơn _Hang động; LLM chấm điểm_

### Mũi Né

**70 điểm** — ưu tiên 1: 7; ưu tiên 2: 2; ưu tiên 3: 61.

| Loại | Số |
| --- | --- |
| Danh thắng | 36 |
| Di tích | 19 |
| Đền / chùa | 2 |
| Bảo tàng | 9 |
| Bãi biển | 1 |
| Núi | 2 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 5 |
| LLM chấm điểm | 7 |
| Quy tắc ít nổi | 11 |
| OSM chưa chấm | 47 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Bảo Tàng Hồ Chí Minh _Bảo tàng; Wikipedia_
- Bảo tàng Lực lượng vũ trang nhân dân _Bảo tàng; Wikipedia_
- Tháp Pô Sah Inư _Danh thắng; Wikipedia_
- Tượng Phật Bà _Di tích; Wikipedia_
- Vạn Thủy Tú _Đền / chùa; Wikipedia_
- White Dunes _Danh thắng; LLM chấm điểm_
- Đồi cát bay Mũi Né _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 2 điểm**

- Ta Cu Moutain _Danh thắng; LLM chấm điểm_
- Trung tâm cứu hộ linh trưởng Đảo Tiên _Danh thắng; LLM chấm điểm_

### Sa Pa

**63 điểm** — ưu tiên 1: 8; ưu tiên 2: 0; ưu tiên 3: 55.

| Loại | Số |
| --- | --- |
| Danh thắng | 44 |
| Di tích | 7 |
| Đền / chùa | 1 |
| Bảo tàng | 6 |
| Núi | 2 |
| Công viên | 2 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 2 |
| Di sản / Wikidata | 3 |
| Curated | 2 |
| LLM chấm điểm | 3 |
| Quy tắc ít nổi | 1 |
| OSM chưa chấm | 52 |

**Nổi tiếng (ưu tiên 1) — 8 điểm**

- Bản Cát Cát _Danh thắng; Curated_
- Carved Boulder Museum _Bảo tàng; Wikipedia_
- Núi Fansipan _Núi; Curated_
- Vườn quốc gia Bát Xát _Công viên; Di sản / Wikidata_
- Vườn quốc gia Hoàng Liên _Công viên; Di sản / Wikidata_
- Vườn quốc gia Hoàng Liên _Danh thắng; Di sản / Wikidata_
- Y Tý _Danh thắng; LLM chấm điểm_
- Đền Bảo Hà _Đền / chùa; Wikipedia_

### Quy Nhơn

**62 điểm** — ưu tiên 1: 9; ưu tiên 2: 1; ưu tiên 3: 52.

| Loại | Số |
| --- | --- |
| Danh thắng | 30 |
| Di tích | 20 |
| Đền / chùa | 2 |
| Bảo tàng | 4 |
| Bãi biển | 5 |
| Núi | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 9 |
| LLM chấm điểm | 2 |
| Quy tắc ít nổi | 3 |
| OSM chưa chấm | 48 |

**Nổi tiếng (ưu tiên 1) — 9 điểm**

- Bảo Tàng Tổng Hợp Bình Định _Bảo tàng; Wikipedia_
- Kỳ Co _Bãi biển; Wikipedia_
- Tháp Bánh Ít _Di tích; Wikipedia_
- Tháp Bình Lâm _Di tích; Wikipedia_
- Tháp Cánh Tiên _Di tích; Wikipedia_
- Tháp Dương Long _Di tích; Wikipedia_
- Tháp Phú Lốc _Di tích; Wikipedia_
- Tháp Thủ Thiện _Di tích; Wikipedia_
- Tháp Đôi _Di tích; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 1 điểm**

- Đập Dâng Văn Phong _Danh thắng; LLM chấm điểm_

### Tây Ninh

**60 điểm** — ưu tiên 1: 7; ưu tiên 2: 1; ưu tiên 3: 52.

| Loại | Số |
| --- | --- |
| Danh thắng | 26 |
| Di tích | 17 |
| Đền / chùa | 3 |
| Bảo tàng | 8 |
| Núi | 2 |
| Hang động | 1 |
| Công viên | 2 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 4 |
| Di sản / Wikidata | 1 |
| LLM chấm điểm | 6 |
| Quy tắc ít nổi | 6 |
| OSM chưa chấm | 43 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Di tích Khám đường Tây Ninh _Bảo tàng; Wikipedia_
- Khu du lịch Núi Bà Đen _Giải trí; LLM chấm điểm_
- Khu vực của Tòa Thánh Đại Đạo Tam Kỳ Phổ Độ _Danh thắng; Wikipedia_
- Nhà Đốc phủ sứ Nguyễn Văn Kiên _Bảo tàng; Wikipedia_
- Vườn quốc gia Lò Gò - Xa Mát _Danh thắng; LLM chấm điểm_
- Vườn quốc gia Lò Gò-Xa Mát _Công viên; Di sản / Wikidata_
- leo rừng _Danh thắng; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 1 điểm**

- Động Thanh Long _Hang động; LLM chấm điểm_

### Côn Đảo

**58 điểm** — ưu tiên 1: 9; ưu tiên 2: 11; ưu tiên 3: 38.

| Loại | Số |
| --- | --- |
| Danh thắng | 13 |
| Di tích | 15 |
| Bảo tàng | 11 |
| Bãi biển | 18 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| LLM chấm điểm | 34 |
| Quy tắc ít nổi | 8 |
| OSM chưa chấm | 15 |

**Nổi tiếng (ưu tiên 1) — 9 điểm**

- Bãi An Hải _Bãi biển; LLM chấm điểm_
- Bãi Cát Lớn _Bãi biển; LLM chấm điểm_
- Bãi Ông Đụng _Danh thắng; LLM chấm điểm_
- Bãi Đất Dốc _Bãi biển; Wikipedia_
- Bãi Đất Thắm _Bãi biển; LLM chấm điểm_
- Bãi Đầm Trầu _Bãi biển; LLM chấm điểm_
- Mũi Cá Mập _Danh thắng; LLM chấm điểm_
- Nhà tù Côn Đảo _Bảo tàng; LLM chấm điểm_
- Vườn quốc gia Côn Đảo _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 11 điểm**

- Bãi Bàng _Bãi biển; LLM chấm điểm_
- Bãi Dương _Bãi biển; LLM chấm điểm_
- Bãi Vông _Bãi biển; LLM chấm điểm_
- Bảo tàng Côn Đảo _Bảo tàng; LLM chấm điểm_
- Cầu tàu 914 _Danh thắng; LLM chấm điểm_
- Di tích Sở Cò _Bảo tàng; LLM chấm điểm_
- Dinh Chúa Đảo _Bảo tàng; LLM chấm điểm_
- Ong Noé beach _Bãi biển; LLM chấm điểm_
- Trại Phú Bình _Bảo tàng; LLM chấm điểm_
- Trại Phú Hải _Bảo tàng; LLM chấm điểm_
- Trại Phú Sơn _Bảo tàng; LLM chấm điểm_

### Đồng Hới

**51 điểm** — ưu tiên 1: 6; ưu tiên 2: 8; ưu tiên 3: 37.

| Loại | Số |
| --- | --- |
| Danh thắng | 19 |
| Di tích | 17 |
| Đền / chùa | 1 |
| Bảo tàng | 8 |
| Bãi biển | 2 |
| Hang động | 4 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| LLM chấm điểm | 32 |
| Quy tắc ít nổi | 10 |
| OSM chưa chấm | 8 |

**Nổi tiếng (ưu tiên 1) — 6 điểm**

- Bao Ninh Beach _Danh thắng; LLM chấm điểm_
- Bãi biển Nhật Lệ _Bãi biển; LLM chấm điểm_
- Chứng tích nhà thờ Tam tòa _Đền / chùa; Wikipedia_
- Nhat Le Beach _Bãi biển; LLM chấm điểm_
- Plage de da nhai _Danh thắng; LLM chấm điểm_
- Quảng trường Hồ chí Minh _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 8 điểm**

- Bảo tàng chiến thắng Khe Sanh _Bảo tàng; LLM chấm điểm_
- Bảo tàng lịch sử Cầu Hiền Lương _Bảo tàng; LLM chấm điểm_
- Bảo tàng tổng hợp tỉnh Quảng Trị _Bảo tàng; LLM chấm điểm_
- Khu bảo tồn thiên nhiên Bắc Hướng Hóa _Danh thắng; LLM chấm điểm_
- Khu dự trữ thiên nhiên Động Châu - Khe Nước Trong _Danh thắng; LLM chấm điểm_
- Tuong Dai _Danh thắng; LLM chấm điểm_
- Vịnh Mốc Tunnels Museum _Bảo tàng; LLM chấm điểm_
- Đền tưởng niệm các chiến sỹ Trường Sơn _Danh thắng; LLM chấm điểm_

### Buôn Ma Thuột

**47 điểm** — ưu tiên 1: 7; ưu tiên 2: 0; ưu tiên 3: 40.

| Loại | Số |
| --- | --- |
| Danh thắng | 23 |
| Di tích | 13 |
| Bảo tàng | 3 |
| Hang động | 2 |
| Công viên | 4 |
| Giải trí | 2 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 2 |
| Di sản / Wikidata | 5 |
| Quy tắc ít nổi | 7 |
| OSM chưa chấm | 33 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Temple dinh lac giao _Danh thắng; Wikipedia_
- Tượng Đài Chiến Thắng Buôn Ma Thuột _Di tích; Wikipedia_
- Vườn quốc gia Bù Gia Mập _Công viên; Di sản / Wikidata_
- Vườn quốc gia Bù Gia Mập _Danh thắng; Di sản / Wikidata_
- Vườn quốc gia Chư Yang Sin _Công viên; Di sản / Wikidata_
- Vườn quốc gia Yok Đôn _Công viên; Di sản / Wikidata_
- Vườn quốc gia Yok Đôn _Danh thắng; Di sản / Wikidata_

### Đồng Văn

**47 điểm** — ưu tiên 1: 0; ưu tiên 2: 0; ưu tiên 3: 47.

| Loại | Số |
| --- | --- |
| Danh thắng | 38 |
| Di tích | 2 |
| Bảo tàng | 1 |
| Hang động | 3 |
| Chợ | 2 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Quy tắc ít nổi | 2 |
| OSM chưa chấm | 45 |

*Không có điểm ưu tiên 1.*

### Nam Định

**45 điểm** — ưu tiên 1: 8; ưu tiên 2: 2; ưu tiên 3: 35.

| Loại | Số |
| --- | --- |
| Danh thắng | 25 |
| Di tích | 9 |
| Đền / chùa | 2 |
| Bảo tàng | 8 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 6 |
| Di sản / Wikidata | 1 |
| LLM chấm điểm | 5 |
| Quy tắc ít nổi | 6 |
| OSM chưa chấm | 27 |

**Nổi tiếng (ưu tiên 1) — 8 điểm**

- Bảo tàng Dệt may Việt Nam _Bảo tàng; Wikipedia_
- Bảo tàng tỉnh Hưng Yên _Bảo tàng; Wikipedia_
- Bảo tàng tỉnh Hưng Yên - cơ sở 2 _Bảo tàng; Wikipedia_
- Bảo tàng tỉnh Nam Đinh _Bảo tàng; Di sản / Wikidata_
- Chùa Keo _Danh thắng; Wikipedia_
- Làng nghề trống Đọi Tam _Danh thắng; Wikipedia_
- Sun World Hà Nam _Giải trí; LLM chấm điểm_
- Vườn quốc gia Xuân Thủy _Danh thắng; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 2 điểm**

- làng làm bún Phòng Lộc Tây _Danh thắng; LLM chấm điểm_
- làng nghề bánh đa nem Chều _Danh thắng; LLM chấm điểm_

### Tuy Hòa

**45 điểm** — ưu tiên 1: 8; ưu tiên 2: 3; ưu tiên 3: 34.

| Loại | Số |
| --- | --- |
| Danh thắng | 27 |
| Di tích | 9 |
| Bảo tàng | 3 |
| Bãi biển | 3 |
| Núi | 1 |
| Công viên | 1 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 12 |
| Quy tắc ít nổi | 5 |
| OSM chưa chấm | 25 |

**Nổi tiếng (ưu tiên 1) — 8 điểm**

- Bãi Xép _Danh thắng; LLM chấm điểm_
- Biển Đại Lãnh _Bãi biển; LLM chấm điểm_
- Bãi Dũng Bầu _Danh thắng; LLM chấm điểm_
- Bãi Môn _Bãi biển; LLM chấm điểm_
- Bãi biển Gành Đỏ _Bãi biển; LLM chấm điểm_
- Tháp Nhạn _Di tích; Wikipedia_
- Vườn quốc gia Ea Sô _Công viên; Di sản / Wikidata_
- Vườn quốc gia Ea Sô _Danh thắng; Di sản / Wikidata_

**Nên gợi ý (ưu tiên 2) — 3 điểm**

- Bảo tàng Phú Yên _Bảo tàng; LLM chấm điểm_
- Di tích lịch sử tàu không số. _Bảo tàng; LLM chấm điểm_
- Địa Đạo Gò Thì Thùng _Bảo tàng; LLM chấm điểm_

### Châu Đốc

**44 điểm** — ưu tiên 1: 7; ưu tiên 2: 8; ưu tiên 3: 29.

| Loại | Số |
| --- | --- |
| Danh thắng | 13 |
| Di tích | 19 |
| Bảo tàng | 8 |
| Hang động | 1 |
| Công viên | 1 |
| Giải trí | 2 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 5 |
| LLM chấm điểm | 19 |
| Quy tắc ít nổi | 9 |
| OSM chưa chấm | 11 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Bảo tàng An Giang _Bảo tàng; LLM chấm điểm_
- Di chỉ Giồng Cát _Di tích; Wikipedia_
- Di chỉ Nền Chùa _Di tích; Wikipedia_
- Khu Trưng bày Tội ác Chiến tranh của Poltpot _Bảo tàng; Wikipedia_
- Nhà trưng bày cổ vật _Bảo tàng; Wikipedia_
- Núi Sam _Danh thắng; LLM chấm điểm_
- Vườn quốc gia Tràm Chim _Danh thắng; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 8 điểm**

- Công viên nước Hải Đến _Giải trí; LLM chấm điểm_
- Công viên nước Thanh Long _Giải trí; LLM chấm điểm_
- Hồ Tà Pạ _Danh thắng; LLM chấm điểm_
- KDL Lâm Viên Núi Cấm _Danh thắng; LLM chấm điểm_
- Khu bảo tồn đất ngập nước Láng Sen _Danh thắng; LLM chấm điểm_
- Lên 5 ông _Danh thắng; LLM chấm điểm_
- Năm Giếng _Danh thắng; LLM chấm điểm_
- đình thần VTT _Danh thắng; LLM chấm điểm_

### Cao Bằng

**40 điểm** — ưu tiên 1: 7; ưu tiên 2: 5; ưu tiên 3: 28.

| Loại | Số |
| --- | --- |
| Danh thắng | 23 |
| Di tích | 8 |
| Đền / chùa | 1 |
| Bảo tàng | 2 |
| Hang động | 5 |
| Công viên | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 3 |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 12 |
| Quy tắc ít nổi | 4 |
| OSM chưa chấm | 19 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Bến thuyền đi Thác Bản Giốc(1) _Danh thắng; Wikipedia_
- Bến thuyền đi Thác Bản Giốc(2) _Danh thắng; LLM chấm điểm_
- Hồ Ba Bể _Di tích; Di sản / Wikidata_
- Truc Lam Phat Tich Pagoda _Đền / chùa; LLM chấm điểm_
- Vườn quốc gia Ba Bể _Danh thắng; Wikipedia_
- Vườn quốc gia Phia Oắc - Phia Đén _Công viên; Di sản / Wikidata_
- Động Ngườm Ngao _Hang động; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 5 điểm**

- Bảo tàng Pắc Bó _Bảo tàng; LLM chấm điểm_
- Bảo tàng tỉnh Cao Bằng _Bảo tàng; LLM chấm điểm_
- Cổng Trời Ngũ Lão _Danh thắng; LLM chấm điểm_
- Khu di tích lịch sử chiến thắng Đông Khê _Danh thắng; LLM chấm điểm_
- Núi Thủng _Danh thắng; LLM chấm điểm_

### Cát Bà

**37 điểm** — ưu tiên 1: 8; ưu tiên 2: 7; ưu tiên 3: 22.

| Loại | Số |
| --- | --- |
| Danh thắng | 18 |
| Di tích | 1 |
| Bãi biển | 7 |
| Hang động | 10 |
| Công viên | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 2 |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 22 |
| Quy tắc ít nổi | 1 |
| OSM chưa chấm | 10 |

**Nổi tiếng (ưu tiên 1) — 8 điểm**

- Bãi biển Cát Cỏ 1 _Bãi biển; LLM chấm điểm_
- Bãi biển Cát Cỏ 2 _Bãi biển; LLM chấm điểm_
- Bãi biển Cát Cỏ 3 _Bãi biển; LLM chấm điểm_
- Hang Sửng Sốt _Hang động; Wikipedia_
- TAJ lake _Danh thắng; Wikipedia_
- Vườn quốc gia Cát Bà _Công viên; Di sản / Wikidata_
- Vườn quốc gia Cát Bà _Danh thắng; Di sản / Wikidata_
- Động Mê Cung _Hang động; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 7 điểm**

- Bãi biển Tùng Thu _Bãi biển; LLM chấm điểm_
- Cai Beo _Danh thắng; LLM chấm điểm_
- Hang Nic _Hang động; LLM chấm điểm_
- Hang Quân Y _Hang động; LLM chấm điểm_
- Hang Tiên Ông _Danh thắng; LLM chấm điểm_
- Hang Trinh Nủ _Hang động; LLM chấm điểm_
- Hospital Cave _Danh thắng; LLM chấm điểm_

### Hạ Long

**37 điểm** — ưu tiên 1: 7; ưu tiên 2: 0; ưu tiên 3: 30.

| Loại | Số |
| --- | --- |
| Danh thắng | 15 |
| Di tích | 3 |
| Bảo tàng | 4 |
| Bãi biển | 3 |
| Núi | 1 |
| Hang động | 6 |
| Công viên | 2 |
| Giải trí | 3 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 3 |
| Curated | 4 |
| Quy tắc ít nổi | 3 |
| OSM chưa chấm | 27 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Bãi Cháy _Bãi biển; Curated_
- Bảo tàng Quảng Ninh _Bảo tàng; Wikipedia_
- Tháp Đồng Hồ _Danh thắng; Wikipedia_
- Vịnh Hạ Long _Di tích; Curated_
- Vịnh Hạ Long _Danh thắng; Curated_
- Đảo Titop _Danh thắng; Curated_
- Động Thiên Cung _Hang động; Wikipedia_

### Hà Giang

**35 điểm** — ưu tiên 1: 6; ưu tiên 2: 5; ưu tiên 3: 24.

| Loại | Số |
| --- | --- |
| Danh thắng | 27 |
| Di tích | 1 |
| Bảo tàng | 2 |
| Núi | 1 |
| Hang động | 2 |
| Công viên | 1 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 19 |
| Quy tắc ít nổi | 1 |
| OSM chưa chấm | 12 |

**Nổi tiếng (ưu tiên 1) — 6 điểm**

- Cầu treo Khuổi My _Danh thắng; LLM chấm điểm_
- Km0 Hà Giang _Danh thắng; Di sản / Wikidata_
- Lung Khuy Cave _Hang động; Wikipedia_
- Thác số 6 _Danh thắng; LLM chấm điểm_
- Vườn quốc gia Du Già _Công viên; Di sản / Wikidata_
- Vườn quốc gia Du Già - Cao nguyên đá Đồng Văn _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 5 điểm**

- Chợ Trung tâm Hoàng Su Phì _Danh thắng; LLM chấm điểm_
- Công viên nước Hà Giang _Giải trí; LLM chấm điểm_
- Grotte Tien Phuong _Hang động; LLM chấm điểm_
- Tea House of Baiyue Tribes _Danh thắng; LLM chấm điểm_
- Thach Lam Vien - Ha Giang _Danh thắng; LLM chấm điểm_

### Vinh

**32 điểm** — ưu tiên 1: 7; ưu tiên 2: 0; ưu tiên 3: 25.

| Loại | Số |
| --- | --- |
| Danh thắng | 15 |
| Di tích | 8 |
| Bảo tàng | 5 |
| Núi | 1 |
| Hang động | 1 |
| Công viên | 1 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| Di sản / Wikidata | 4 |
| LLM chấm điểm | 5 |
| Quy tắc ít nổi | 2 |
| OSM chưa chấm | 20 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Hương Sơn _Di tích; Di sản / Wikidata_
- Khu di tích lịch sử Kim Liên _Bảo tàng; Di sản / Wikidata_
- Khu lưu niệm Đại Thi Hào Nguyễn Du _Di tích; Wikipedia_
- Thành cổ Vinh _Danh thắng; LLM chấm điểm_
- VinWonder Cửa Hội _Giải trí; LLM chấm điểm_
- Vườn quốc gia Pù Mát _Công viên; Di sản / Wikidata_
- Vườn quốc gia Pù Mát _Danh thắng; Di sản / Wikidata_

### Kon Tum

**31 điểm** — ưu tiên 1: 6; ưu tiên 2: 1; ưu tiên 3: 24.

| Loại | Số |
| --- | --- |
| Danh thắng | 22 |
| Di tích | 6 |
| Bảo tàng | 2 |
| Công viên | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 2 |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 5 |
| Quy tắc ít nổi | 3 |
| OSM chưa chấm | 19 |

**Nổi tiếng (ưu tiên 1) — 6 điểm**

- Nhà Rông Kon Pring _Danh thắng; LLM chấm điểm_
- Tòa giám mục Kon Tum - Chủng viện thừa sai _Danh thắng; Wikipedia_
- Vườn quốc gia Chư Mom Ray _Công viên; Di sản / Wikidata_
- Vườn quốc gia Chư Mom Ray _Danh thắng; Di sản / Wikidata_
- Vườn quốc gia Kon Ka Kinh _Danh thắng; Wikipedia_
- sân bay dã chiến _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 1 điểm**

- Thác Pa Sỹ _Danh thắng; LLM chấm điểm_

### Mai Châu

**31 điểm** — ưu tiên 1: 0; ưu tiên 2: 6; ưu tiên 3: 25.

| Loại | Số |
| --- | --- |
| Danh thắng | 17 |
| Di tích | 5 |
| Bảo tàng | 3 |
| Hang động | 6 |

| Bằng chứng | Số |
| --- | --- |
| LLM chấm điểm | 7 |
| Quy tắc ít nổi | 4 |
| OSM chưa chấm | 20 |

*Không có điểm ưu tiên 1.*

**Nên gợi ý (ưu tiên 2) — 6 điểm**

- Cave _Hang động; LLM chấm điểm_
- Chùa Hang Bụt _Hang động; LLM chấm điểm_
- Hang Bó Muòi _Hang động; LLM chấm điểm_
- Hang Chiều _Hang động; LLM chấm điểm_
- Hang Nhim Cave _Hang động; LLM chấm điểm_
- Hang Sung _Hang động; LLM chấm điểm_

### Phan Rang

**28 điểm** — ưu tiên 1: 7; ưu tiên 2: 5; ưu tiên 3: 16.

| Loại | Số |
| --- | --- |
| Danh thắng | 9 |
| Di tích | 9 |
| Bảo tàng | 4 |
| Bãi biển | 4 |
| Núi | 2 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 3 |
| LLM chấm điểm | 12 |
| Quy tắc ít nổi | 2 |
| OSM chưa chấm | 11 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Bãi Chuối _Bãi biển; LLM chấm điểm_
- Bãi Chà Là _Bãi biển; LLM chấm điểm_
- Bãi Cà Tiên _Bãi biển; LLM chấm điểm_
- Bãi Tràng _Bãi biển; LLM chấm điểm_
- Tháp Hòa Lai _Di tích; Wikipedia_
- Tháp Po Dam _Di tích; Wikipedia_
- Vườn quốc gia Núi Chúa _Danh thắng; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 5 điểm**

- Bãi Hỏm _Danh thắng; LLM chấm điểm_
- Bảo tàng Ninh Thuận _Bảo tàng; LLM chấm điểm_
- Hang rái _Danh thắng; LLM chấm điểm_
- Mốc 3 tỉnh Lâm đồng - Ninh thuận - Bình thuận 1701m _Danh thắng; LLM chấm điểm_
- Trung Tâm Nghiên Cứu Văn Hóa Chăm _Bảo tàng; LLM chấm điểm_

### Yên Bái

**28 điểm** — ưu tiên 1: 2; ưu tiên 2: 0; ưu tiên 3: 26.

| Loại | Số |
| --- | --- |
| Danh thắng | 15 |
| Di tích | 10 |
| Bảo tàng | 3 |

| Bằng chứng | Số |
| --- | --- |
| Di sản / Wikidata | 1 |
| LLM chấm điểm | 1 |
| Quy tắc ít nổi | 6 |
| OSM chưa chấm | 20 |

**Nổi tiếng (ưu tiên 1) — 2 điểm**

- Bảo tàng tỉnh Yên Bái _Bảo tàng; Di sản / Wikidata_
- tea leaf forests _Danh thắng; LLM chấm điểm_

### Cà Mau

**26 điểm** — ưu tiên 1: 8; ưu tiên 2: 2; ưu tiên 3: 16.

| Loại | Số |
| --- | --- |
| Danh thắng | 14 |
| Di tích | 9 |
| Bảo tàng | 2 |
| Bãi biển | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 2 |
| Di sản / Wikidata | 4 |
| LLM chấm điểm | 9 |
| Quy tắc ít nổi | 4 |
| OSM chưa chấm | 7 |

**Nổi tiếng (ưu tiên 1) — 8 điểm**

- Bảo tàng tỉnh Bạc Liêu _Bảo tàng; Di sản / Wikidata_
- Cột cờ Mũi Cà Mau _Danh thắng; LLM chấm điểm_
- Khu di tích lịch sử Căn cứ Ban An ninh khu IX _Bảo tàng; LLM chấm điểm_
- Tháp Vĩnh Hưng _Di tích; Di sản / Wikidata_
- Vườn quốc gia Mũi Cà Mau _Di tích; Di sản / Wikidata_
- Vườn quốc gia Mũi Cà Mau _Danh thắng; Di sản / Wikidata_
- Vườn quốc gia U Minh Hạ _Danh thắng; Wikipedia_
- Vườn quốc gia U Minh Thượng _Danh thắng; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 2 điểm**

- Bãi Khai Long _Bãi biển; LLM chấm điểm_
- Sân chim Đầm Dơi _Danh thắng; LLM chấm điểm_

### Thanh Hóa

**26 điểm** — ưu tiên 1: 7; ưu tiên 2: 5; ưu tiên 3: 14.

| Loại | Số |
| --- | --- |
| Danh thắng | 20 |
| Di tích | 1 |
| Bảo tàng | 3 |
| Bãi biển | 1 |
| Công viên | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 4 |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 7 |
| OSM chưa chấm | 13 |

**Nổi tiếng (ưu tiên 1) — 7 điểm**

- Bãi biển Sầm Sơn _Bãi biển; Wikipedia_
- Bảo tàng tỉnh Thanh Hóa _Bảo tàng; Wikipedia_
- Thành Nhà Hồ _Danh thắng; Wikipedia_
- Vườn quốc gia Bến En _Công viên; Di sản / Wikidata_
- Vườn quốc gia Bến En _Danh thắng; Di sản / Wikidata_
- Vườn quốc gia Xuân Liên _Danh thắng; LLM chấm điểm_
- khu di tích lịch sử Lam Kinh _Danh thắng; Wikipedia_

**Nên gợi ý (ưu tiên 2) — 5 điểm**

- Làng mộc Đạt Tài _Danh thắng; LLM chấm điểm_
- Làng nghề dệt nhiễu Hồng Đô _Danh thắng; LLM chấm điểm_
- Làng nghề đúc đồng Chè Đông _Danh thắng; LLM chấm điểm_
- Làng điêu khắc đá Nhồi _Danh thắng; LLM chấm điểm_
- Đình Hàm Hạ _Danh thắng; LLM chấm điểm_

### Điện Biên Phủ

**24 điểm** — ưu tiên 1: 0; ưu tiên 2: 0; ưu tiên 3: 24.

| Loại | Số |
| --- | --- |
| Danh thắng | 8 |
| Di tích | 11 |
| Bảo tàng | 3 |
| Hang động | 2 |

| Bằng chứng | Số |
| --- | --- |
| LLM chấm điểm | 1 |
| Quy tắc ít nổi | 7 |
| OSM chưa chấm | 16 |

*Không có điểm ưu tiên 1.*

### Cô Tô

**23 điểm** — ưu tiên 1: 5; ưu tiên 2: 4; ưu tiên 3: 14.

| Loại | Số |
| --- | --- |
| Danh thắng | 12 |
| Di tích | 2 |
| Bãi biển | 6 |
| Núi | 1 |
| Công viên | 1 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Di sản / Wikidata | 2 |
| LLM chấm điểm | 15 |
| Quy tắc ít nổi | 1 |
| OSM chưa chấm | 5 |

**Nổi tiếng (ưu tiên 1) — 5 điểm**

- Bãi Trà Cổ _Bãi biển; LLM chấm điểm_
- Bãi biển Minh Châu _Bãi biển; LLM chấm điểm_
- Thác sông Mooc _Danh thắng; LLM chấm điểm_
- Vườn quốc gia Bái Tử Long _Công viên; Di sản / Wikidata_
- Vườn quốc gia Bái Tử Long _Danh thắng; Di sản / Wikidata_

**Nên gợi ý (ưu tiên 2) — 4 điểm**

- Bãi biển Quan Lạn _Bãi biển; LLM chấm điểm_
- Bãi biển Sơn Hào _Bãi biển; LLM chấm điểm_
- Bãi Đá Đen _Bãi biển; LLM chấm điểm_
- Đền Xã Tắc _Danh thắng; LLM chấm điểm_

### Hà Tĩnh

**23 điểm** — ưu tiên 1: 2; ưu tiên 2: 0; ưu tiên 3: 21.

| Loại | Số |
| --- | --- |
| Danh thắng | 11 |
| Di tích | 6 |
| Bảo tàng | 1 |
| Bãi biển | 1 |
| Núi | 1 |
| Công viên | 2 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| Di sản / Wikidata | 1 |
| Quy tắc ít nổi | 3 |
| OSM chưa chấm | 18 |

**Nổi tiếng (ưu tiên 1) — 2 điểm**

- Bảo tàng tỉnh Hà Tĩnh _Bảo tàng; Di sản / Wikidata_
- Vườn quốc gia Vũ Quang _Danh thắng; Wikipedia_

### Pleiku

**20 điểm** — ưu tiên 1: 4; ưu tiên 2: 3; ưu tiên 3: 13.

| Loại | Số |
| --- | --- |
| Danh thắng | 6 |
| Di tích | 7 |
| Bảo tàng | 4 |
| Núi | 1 |
| Công viên | 1 |
| Giải trí | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| LLM chấm điểm | 8 |
| Quy tắc ít nổi | 5 |
| OSM chưa chấm | 6 |

**Nổi tiếng (ưu tiên 1) — 4 điểm**

- Biển Hồ Pleiku _Danh thắng; LLM chấm điểm_
- Bảo tàng Hồ Chí Minh _Bảo tàng; Wikipedia_
- Khu Du Lịch Đại Vinh Gia Trang _Danh thắng; LLM chấm điểm_
- Núi lửa Chư Đang Ya _Danh thắng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 3 điểm**

- Bảo tàng Binh đoàn Tây Nguyên _Bảo tàng; LLM chấm điểm_
- Bảo tàng Pleiku _Bảo tàng; LLM chấm điểm_
- Bảo tàng Tịch Hồ Chí Minh CN Gia lai _Bảo tàng; LLM chấm điểm_

### Quảng Ngãi

**20 điểm** — ưu tiên 1: 4; ưu tiên 2: 1; ưu tiên 3: 15.

| Loại | Số |
| --- | --- |
| Danh thắng | 7 |
| Di tích | 7 |
| Bảo tàng | 4 |
| Bãi biển | 1 |
| Công viên | 1 |

| Bằng chứng | Số |
| --- | --- |
| Wikipedia | 1 |
| Di sản / Wikidata | 1 |
| Curated | 1 |
| LLM chấm điểm | 5 |
| Quy tắc ít nổi | 3 |
| OSM chưa chấm | 9 |

**Nổi tiếng (ưu tiên 1) — 4 điểm**

- Bãi biển Mỹ Khê _Bãi biển; Curated_
- Huỳnh Công Thiệu _Di tích; Di sản / Wikidata_
- Sa Huỳnh _Danh thắng; Wikipedia_
- Son My / My Lai memorial _Bảo tàng; LLM chấm điểm_

**Nên gợi ý (ưu tiên 2) — 1 điểm**

- Bảo tàng tỉnh Quảng Ngãi _Bảo tàng; LLM chấm điểm_

### Lạng Sơn

**13 điểm** — ưu tiên 1: 1; ưu tiên 2: 0; ưu tiên 3: 12.

| Loại | Số |
| --- | --- |
| Danh thắng | 8 |
| Di tích | 3 |
| Đền / chùa | 1 |
| Bảo tàng | 1 |

| Bằng chứng | Số |
| --- | --- |
| Di sản / Wikidata | 1 |
| Quy tắc ít nổi | 2 |
| OSM chưa chấm | 10 |

**Nổi tiếng (ưu tiên 1) — 1 điểm**

- Bảo tàng tỉnh Lạng Sơn _Bảo tàng; Di sản / Wikidata_

---

Quy tắc thu thập: OSM giữ điểm đã map; Wikipedia / di sản / curated → ưu tiên 1; LLM chỉ chấm id còn lại, không bịa điểm mới.
