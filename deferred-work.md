- source_spec: `spec-mvp-hld-v03.md`
  summary: Chuyển JWT trình duyệt từ localStorage sang cookie HttpOnly/Secure/SameSite với bảo vệ CSRF.
  evidence: Review login xác nhận token bảy ngày hiện đọc được bằng JavaScript; đây là kiến trúc auth có sẵn, cần thay đổi đồng bộ backend/frontend và migration phiên.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Harden ownership phiên ẩn danh bằng session credential ký thay vì UUID localStorage thuần.
  evidence: Review login xác nhận `ma_phien` hiện là bearer identifier dùng để claim dữ liệu; cần contract auth riêng để tránh claim nhầm khi identifier bị lộ.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Thêm cancellation/idempotency xuyên suốt cho tác vụ tạo kế hoạch khi client ngắt stream hoặc timeout.
  evidence: Review Planner xác nhận AbortController chỉ dừng HTTP phía trình duyệt; `to_thread(build_plan, payload)` phía backend vẫn có thể hoàn tất, lưu kế hoạch và phát sinh chi phí trước khi người dùng retry.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Dành trước regeneration nonce nguyên tử trước khi gọi pipeline trên mọi worker.
  evidence: Nonce replay tuần tự hiện trả kết quả trước rate-limit, nhưng hai request đồng thời cùng nonce vẫn có thể cùng vượt `get_nonce` và phát sinh hai lần build/cost; cần pending reservation hoặc distributed lock trong PostgreSQL/Redis.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Chuẩn hóa địa chỉ IP phía client qua trusted-proxy allowlist trước khi dùng cho rate limit.
  evidence: Roadtrip đã giới hạn theo IP và phiên, nhưng `request.client.host` chỉ đáng tin khi topology reverse proxy và forwarded-header policy được cấu hình đồng bộ ở môi trường triển khai.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Proxy hoặc xin consent rõ ràng trước khi tải trực tiếp tile bản đồ OSM từ trình duyệt.
  evidence: RoadTripMap hiện tải tile từ `tile.openstreetmap.org`, làm lộ IP và metadata truy cập cho bên thứ ba; cần tile proxy/cache và chính sách pháp lý ở cấp triển khai.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Áp dụng giới hạn request body toàn dịch vụ trước bước parse JSON.
  evidence: Schema Roadtrip giới hạn số điểm dừng và chuỗi, nhưng ASGI server vẫn có thể nhận body JSON quá lớn trước khi Pydantic từ chối; cần middleware/server ingress limit dùng chung.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Truyền cancellation và deadline xuyên suốt các lời gọi provider của Multi-city/Roadtrip.
  evidence: Abort ở trình duyệt không đảm bảo dừng công việc backend hoặc chi phí provider; cần structured cancellation, deadline budget và idempotency dùng chung.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Làm nguyên tử việc tiêu thụ đồng thời quota IP và quota phiên.
  evidence: Hai lần kiểm tra Redis riêng biệt có thể tiêu thụ quota thứ nhất dù quota thứ hai từ chối; cần Lua script hoặc transaction dùng chung cho multi-key limiter.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Hậu kiểm ngôn ngữ và factual claims của phần copy do AI sinh.
  evidence: Prompt đã khóa id, tên riêng, nguồn và dữ kiện định lượng, nhưng production AI vẫn cần language detector và claim policy để ngăn mô tả sai ngôn ngữ hoặc thêm khẳng định chưa có nguồn.

- source_spec: `spec-mvp-hld-v03.md`
  summary: Dùng font và shaping engine đầy đủ cho PDF Arabic, Hebrew, Indic và CJK.
  evidence: PDF đã có nhãn đủ 19 locale nhưng ReportLab/Arial hoặc DejaVu không bảo đảm shaping và glyph coverage hoàn chỉnh trên mọi máy production; cần font bundle được cấp phép và visual golden tests từng hệ chữ.
