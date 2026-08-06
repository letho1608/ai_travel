# Capability parity matrix — Layla.ai

Ngày đối chiếu: 2026-08-05. Nguồn công khai: `https://layla.ai/about`, `https://layla.ai/faq`.

`Đạt code` nghĩa là implementation và test đã có; `Đạt live` chỉ dùng khi đã chạy với provider production thật.

| Capability công khai của Layla | Trạng thái hiện tại | Bằng chứng / khoảng trống |
|---|---|---|
| Chat lập lịch cá nhân hóa theo ngày | Đạt code | `backend/app/pipeline/planner.py`, `frontend/components/PlanView.tsx` |
| Tinh chỉnh hội thoại theo ngân sách/số người/phong cách | Đạt code | `POST /api/plans/{token}/refine`; version history + restore |
| Bản đồ tương tác và tuyến tối ưu | Đạt live trong Hà Nội | OSM 3.508 POI; OSRM 2.450 cạnh; map↔timeline selection |
| Dự báo thời tiết | Đạt live | Open‑Meteo có retry, provenance và fallback an toàn |
| Chuyến bay live | Đạt code, chưa đạt live | Amadeus Flight Offers adapter; cần production credentials |
| Khách sạn live | Đạt code, chưa đạt live | Hotel List→Hotel Offers v3; cần production credentials |
| Activities live và booking link | Đạt code, chưa đạt live | Amadeus Activities adapter; chỉ giữ HTTPS provider link |
| Snapshot giá/availability có expiry | Đạt code | PostgreSQL `inventory_snapshot`, TTL 15 phút |
| Booking/human assistance | Đạt code, chưa đạt live | Hàng đợi `/support`, staff-token, phân công, state machine và audit history bền vững; luôn trả `booking_confirmed=false`; cần nhân sự thật và provider/CRM production |
| Google OAuth, lưu chuyến và đồng bộ thiết bị | Đạt code, chưa đạt live | Google ID-token verifier + JWT + anonymous merge; cần client ID/secrets |
| Chia sẻ và collaboration | Đạt code | Read-only share, comments, owner-only resolve, version restore |
| Tải/offline | Đạt code | PDF Unicode đã render/QA, iCalendar, JSON, local snapshot, service-worker cached visited plans |
| Nhắc trước chuyến và feedback sau chuyến | Đạt code | Worker định kỳ tạo thông báo nhắc trước 24h vào PostgreSQL; inbox theo chủ sở hữu, trạng thái đã đọc; feedback sau chuyến duy nhất theo chủ sở hữu |
| Multi-city và road trip | Đạt code, route đạt live | UI/API ghép OSRM với flight + hotel snapshot theo IATA/ngày cho tối đa 6 thành phố, round-trip và báo completeness; cần Amadeus production credentials, train provider và day itinerary giữa chặng để đạt live toàn phần |
| Trains, car rental, private transfer | Một phần | Private/shared/taxi/airport-express Transfer Search đã nối Amadeus và snapshot; car rental cần Amadeus Enterprise Cars, train cần licensed rail provider; tất cả còn cần credentials production |
| Flight price prediction | Đạt code, chưa đạt live | Flight Offers được ghép với Amadeus Itinerary Price Metrics (AI trên historical fares), gồm quartile/currency và fail-closed; cần production credentials để xác minh live |
| Smart hotel filters | Đạt code, chưa đạt live | Hạng sao/tiện nghi được gửi vào Hotel List API; bán kính và khoảng giá được kiểm tra định lượng; cần Amadeus production credentials để chạy live |
| 16 ngôn ngữ/currency/units | Một phần | Preference hỗ trợ 16 locale Layla + vi/ko/th; toàn bộ UI, Roadtrip/Multi-city, nội dung itinerary, thời tiết, PDF/ICS và phản hồi mutation đã có contract đủ 19 locale với `lang`/RTL; chi phí plan vẫn hiển thị VND để không giả tỷ giá, production AI còn cần kiểm chứng chất lượng ngôn ngữ thực tế |
| Video map và creator media | Chưa đạt | Cần licensed media/provider và moderation pipeline |
| PDF itinerary | Đạt code | API trả PDF A4 có nguồn, lịch từng ngày và Unicode tiếng Việt; đã kiểm tra trực quan bản render |
| Production security/performance/legal audit | Một phần | Consent/Privacy/Terms, xóa tài khoản atomic + revoke JWT, CSP/HSTS/frame/referrer/permissions headers, request-id, no-store API và gzip đã có; còn thiếu pháp nhân/đầu mối dữ liệu, legal review, deploy target và load/E2E production run |

## Quy tắc hoàn thành

Parity 100% chưa được tuyên bố cho đến khi mọi dòng là `Đạt live`, hoặc được người dùng loại khỏi phạm vi bằng quyết định rõ ràng. Capability đối chiếu theo hành vi, không sao chép thương hiệu, nội dung, mã nguồn hay tài sản của Layla.
