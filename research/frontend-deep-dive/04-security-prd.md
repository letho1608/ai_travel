# Audit Security & Production Readiness - Frontend Next.js

## Findings

### 1. XSS & Rendering

*   **File:** Không tìm thấy `dangerouslySetInnerHTML` trong `frontend/components` và `frontend/app`.
*   **Mức độ:** Low.
*   **Phân tích:** Ứng dụng dường như không render HTML thô từ API backend (ít nhất là qua `dangerouslySetInnerHTML`). `DOMPurify` cũng không có trong `package.json`. Nội dung API (như `plan.tieu_de`, `plan.tom_tat`) được truyền thẳng vào props React (`<PlanView initial={d.ke_hoach} ... />`), mặc định React đã escape text.
*   **Đề xuất:** Xác nhận lại các field markdown nếu có. Nếu có render markdown trong tương lai, cần dùng thư viện sanitize (như `dompurify` hoặc `rehype-sanitize`).

### 2. Auth & Session Management

*   **File:** `frontend/lib/session.ts`, `frontend/app/login/page.tsx`
*   **Mức độ:** High.
*   **Phân tích:**
    *   Token (`auth_token`) và Session ID (`ma_phien`) được lưu trong `localStorage`. Điều này khiến chúng dễ bị tấn công XSS trộm (Local Storage không có cơ chế `httpOnly`).
    *   Không thấy sử dụng HTTP-only cookies cho `auth_token` và `ma_phien`.
    *   Lưu ý: API Google OAuth `submitToken` tại `frontend/app/login/page.tsx` gửi token về backend và nhận `data.token`, sau đó ghi vào `localStorage`.
*   **Đề xuất:**
    *   Chuyển `auth_token` sang `httpOnly` cookie thông qua Next.js API Routes (hoặc backend FastAPI set cookie trực tiếp với `Set-Cookie` header).
    *   Backend cần trả về `Set-Cookie: auth_token=...; HttpOnly; Secure; SameSite=Lax`.

### 3. Backend Admin Authorization (/admin)

*   **File:** `frontend/app/admin/page.tsx` và `backend/app/routers/admin.py`
*   **Mức độ:** Medium.
*   **Phân tích:**
    *   Client `frontend/app/admin/page.tsx` yêu cầu người dùng nhập `token` (vào field "Admin token"), lưu vào `sessionStorage` (`admin_token`, `support_token`), và gửi qua header `X-Admin-Token`.
    *   Backend `backend/app/routers/admin.py` hàm `authorize_admin` kiểm tra header này so với `settings.support_admin_token` dùng `secrets.compare_digest` (an toàn chống timing attack).
    *   Tuy nhiên, token là 1 string cố định (static token), có nguy cơ brute-force nếu không giới hạn rate limit chặt (không thấy rate limit ở endpoint `/dashboard` hoặc middleware global cho admin).
*   **Đề xuất:** Cấu hình rate limit chặt chẽ cho tất cả routes `/api/admin/*` hoặc bảo vệ thư mục `/admin` bằng SSO / OAuth thay vì static token.

### 4. PWA / Service Worker Caching

*   **File:** `frontend/public/sw.js`
*   **Mức độ:** Medium.
*   **Phân tích:**
    *   Service Worker cache chiến lược "network first, fallback to cache" cho mọi request `GET` cùng origin.
    *   `caches.open(CACHE).then(cache => cache.put(request, response.clone()))` sẽ cache lại mọi thứ, bao gồm cả `/api/plans/*` nếu Next.js fetch từ client, hoặc các page HTML có chứa dữ liệu nhạy cảm của người dùng (ví dụ `/history`, `/settings`). Mặc dù SW đang chặn `request.url` khác origin, nhưng Next.js routes (cùng origin) có thể chứa private data.
*   **Đề xuất:** Không cache các endpoint chứa private data. Chỉ cache statics asset, manifest, và app shell.

### 5. Plan Sharing ([token])

*   **File:** `backend/app/routers/plans.py`, `frontend/app/plan/[token]/page.tsx`, `backend/app/services/store.py`
*   **Mức độ:** Low.
*   **Phân tích:**
    *   Plan được chia sẻ qua URL chứa `token` (VD: `/plan/[token]`).
    *   Backend `store.py` hàm `save` tạo token bằng `str(uuid4())` (UUIDv4) rất an toàn, khó brute-force.
    *   Endpoint `/api/plans/{token}` không cần Auth để đọc. Ai có URL đều đọc được (by design cho sharing).
*   **Đề xuất:** Cơ chế hiện tại an toàn. Đảm bảo user hiểu rủi ro khi chia sẻ URL (bất kỳ ai có link đều xem được).

### 6. Mixed Content, CORS & Metadata

*   **File:** `backend/app/main.py`, `frontend/app/plan/[token]/page.tsx`
*   **Mức độ:** Low.
*   **Phân tích:**
    *   Backend FastAPI set CORS: `allow_origins=list(settings.cors_origins)`, `allow_credentials=True`. Config có vẻ chuẩn.
    *   Backend CSP: `default-src 'none'; frame-ancestors 'none'`. Rất chặt chẽ.
    *   Next.js `generateMetadata` sử dụng `BASE_URL ?? "http://localhost:3000"`, đảm bảo metadata không bị leak sai origin trên production. `fetch` gọi API nội bộ dùng `no-store` để tránh caching nhầm data user.

## Summary

Ứng dụng có kiến trúc bảo mật tương đối tốt nhưng vẫn còn những điểm yếu cần khắc phục, đặc biệt là việc quản lý Session/Token bằng LocalStorage. Việc dùng LocalStorage làm cho token có rủi ro bị đánh cắp nếu xuất hiện lỗ hổng XSS trong tương lai (mặc dù hiện tại Next.js chống XSS khá tốt). Admin panel sử dụng static token cần bổ sung rate limit để tránh brute-force. Service worker caching cần loại trừ những route nhạy cảm để không lưu lọt vào cache thiết bị. Các cơ chế khác như CORS, CSP headers từ Backend đã được thiết lập chặt chẽ.

Confidence: 8/10.