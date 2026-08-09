# Executive Briefing: Frontend Codebase Audit

**TL;DR:** Kiến trúc Next.js (App Router) và hệ thống đa ngôn ngữ (i18n) của frontend được xây dựng rất vững chắc. Tuy nhiên, ứng dụng hiện tại đang gặp các lỗ hổng nghiêm trọng về UX và độ ổn định (thiếu timeout SSR, hardcode tọa độ tìm kiếm, race conditions khi gọi API) có thể dẫn tới sập luồng (crash) hoặc trải nghiệm người dùng đứt gãy. **Chưa đủ điều kiện (Not ready) để đưa lên môi trường Production.**

**Confidence:** 6/10 — Khung sườn kiến trúc tốt, nhưng các chi tiết triển khai cụ thể còn nhiều lỗi nguy hiểm.
*(Ground-truth tally: 7/7 load-bearing conclusions dựa trên đọc và xác minh mã nguồn thực tế; 0 dựa trên dự đoán mô hình).*

---

## 1. Điểm sáng (What Works Well)
*   **Đa ngôn ngữ (i18n):** Hệ thống 19 ngôn ngữ được thiết lập rất đầy đủ và nhất quán ở các layer components.
*   **Routing & UI:** App Router sử dụng tốt, giao diện Dark Mode/Responsive làm chuẩn mực.

---

## 2. Các vấn đề cốt lõi (Critical Findings)

### Tier 0: BLOCKERS (Phải sửa trước khi golive)
1. **Sập server SSR do thiếu Timeout:** 
   * `frontend/app/plan/[token]/page.tsx` gọi `fetch` API trên server mà không có cơ chế timeout (`AbortSignal.timeout()`). Nếu Backend treo, toàn bộ worker SSR của Next.js sẽ bị cạn kiệt, làm sập Frontend.
2. **Liệt tính năng tìm kiếm (Hardcode tọa độ):**
   * `frontend/app/explore/page.tsx` đang gán cứng payload tọa độ `{latitude:21.0285,longitude:105.8542}` (Hà Nội) khi tìm Hotel/Activity, khiến ứng dụng hoàn toàn không thể tìm kiếm ở các địa điểm khác.
3. **Mất thông báo lỗi thật từ Backend:**
   * `frontend/lib/api.ts` (hàm parse error): Logic trong block `catch` lại đi cố `JSON.parse` một lần nữa chuỗi vừa gây lỗi, dẫn đến luôn văng `SyntaxError`, làm UI nuốt mất thông điệp báo lỗi thật (như lỗi rate-limit, lỗi token).

### Tier 1: HIGH (Ưu tiên cao)
4. **Race Condition & Spam Click:**
   * `frontend/components/Planner.tsx`: Khi nhấn nút Submit liên tục, request cũ không bị `.abort()`, tạo ra vô số request chạy ngầm lãng phí tài nguyên và xung đột trạng thái.
   * `frontend/components/PlanView.tsx`: Dính "Stale Closure" biến `ver` (phiên bản), khiến user thao tác nhanh sẽ bị backend từ chối vì gửi nhầm phiên bản cũ.
5. **Nuốt lỗi 401 (Chưa chuyển hướng đăng nhập):**
   * `frontend/app/explore/page.tsx` và Planner bắt được mã 401 nhưng chỉ xóa token mà không chuyển hướng người dùng về trang `/login` (thiếu `router.push`).
6. **Bảo mật Session:**
   * `auth_token` đang lưu ở `localStorage` dễ bị tấn công XSS. URL chia sẻ Plan (`/plan/[token]`) có thể bị lọt ra ngoài qua HTTP Referer. Cần chuyển token sang HTTP-Only Cookie.

### Tier 2: MEDIUM (Nên sửa để tăng UX)
7. **Tràn RAM (Memory Leak) / Giật màn hình bản đồ:**
   * `frontend/components/MapView.tsx` đang dọn dẹp (destroy) và vẽ lại toàn bộ bản đồ mỗi khi user đổi marker được chọn, thay vì chỉ đổi màu marker, gây giật (flicker) và hao tài nguyên.
8. **Khựng giao diện (Main Thread block):**
   * Lưu chuỗi JSON lớn của toàn bộ Plan vào `localStorage` trong lúc render một cách đồng bộ. Nên dùng `IndexedDB` bất đồng bộ.

---

## 3. Khuyến nghị hành động (Next Steps)

Nên triển khai các sửa đổi theo thứ tự sau:
1. **Fix Tier 0 (Blockers):** Bổ sung `AbortSignal` cho fetch SSR, mở khóa truyền parameter linh hoạt cho `Explore`, và sửa lại khối try-catch trong `api.ts`.
2. **Fix Tier 1 (State & Auth):** Chèn `controllerRef.current?.abort()` trước khi gửi request mới; bọc biến version bằng `useRef()`; bổ sung `router.push('/login')` toàn cục.
3. **Audit bảo mật:** Đưa token vào cookie thay vì LocalStorage để cắt đứt rủi ro XSS. 

*Tất cả báo cáo chi tiết theo từng góc độ (Data, UX, CSS/i18n, Security, Synthesis, Red-team) đã được lưu vào thư mục `D:\Code\aithucchien\ai_travel\research\frontend-deep-dive\` để developer tham chiếu.*