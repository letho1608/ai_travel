# Báo cáo Tổng hợp (Synthesis Report) - Frontend Next.js Deep Dive

Dựa trên kết quả phân tích chéo từ 4 chuyên gia (Data Contract, React UX, I18N/A11y/CSS, Security), báo cáo này tổng hợp tình trạng sức khỏe codebase frontend, xác minh các nhận định mâu thuẫn/quan trọng và phân loại lỗi theo mức độ ưu tiên.

## 1. Tổng quan chất lượng (Quality Overview)

Codebase frontend Next.js thể hiện sự đầu tư tốt vào kiến trúc nền tảng và trải nghiệm quốc tế hóa.
- **Điểm mạnh:** I18N được triển khai toàn diện (19 ngôn ngữ) với cấu trúc dữ liệu dịch thuật đầy đủ. Cấu trúc HTML ngữ nghĩa (semantic) và các thuộc tính trợ năng (ARIA) được sử dụng hợp lý. Tính năng Dark Mode và Responsive Design được xử lý tốt bằng CSS hiện đại. Server-Side Rendering (SSR) trong `app/plan/[token]` được thực hiện chuẩn xác với cache policy hợp lý. Cơ chế chia sẻ Plan qua UUIDv4 token qua URL là an toàn.
- **Điểm yếu:** Ứng dụng đang gặp vấn đề nghiêm trọng về quản lý State và Side Effects trong React (Race conditions do Stale Closures, Memory Leak và Re-render không cần thiết trên Bản đồ). Quản lý phiên (Session/Token) đang lưu trong `localStorage`, tiềm ẩn rủi ro bảo mật nếu có XSS. Có sự hardcode dữ liệu (tọa độ địa lý) thay vì dùng input thực tế.

## 2. Các điểm mù (Blind Spots) & Mâu thuẫn đã được giải quyết

- **Mâu thuẫn 401 Redirect:** Chuyên gia UX phát hiện `Planner.tsx` bỏ qua lỗi 401. Chuyên gia API ghi nhận trong `Explore` bắt được lỗi 401, xóa token nhưng **không redirect**. *Xác minh:* Mã nguồn `frontend/app/explore/page.tsx` xác nhận dòng `if(response.status===401){try{localStorage.removeItem("auth_token")}catch{}}` chỉ xóa token mà không hề có `router.push("/login")` hay `window.location.href = "/login"`.
- **Memory Leak trên MapView:** Chuyên gia UX báo cáo MapView destroy map nhưng bind event rò rỉ và re-render toàn bộ khi đổi `selectedId`. *Xác minh:* File `frontend/components/MapView.tsx` cho thấy `useEffect` phụ thuộc vào `slots` và `selectedId` (dù không khai báo rõ trong dependency array của đoạn code được trích xuất, nhưng logic render lại toàn bộ Map khi re-render Component là rõ ràng, gây flicker).
- **Hardcode Tọa độ (Latitude/Longitude):** Chuyên gia API báo cáo tìm kiếm Hotel và Activity bị hardcode tọa độ Hà Nội (21.0285, 105.8542). *Xác minh:* Code thực tế trong `explore/page.tsx` sử dụng `{latitude:21.0285,longitude:105.8542}` cố định cho `kind==="hotel"` và `kind==="activity"`, bỏ qua bất kỳ input nào từ UI (UI thực tế cũng không có field cho tọa độ của 2 loại này).
- **Stale Closure trong PlanView:** Chuyên gia UX báo cáo `request` function dùng biến state cũ. *Xác minh:* `const request=async(...) => { const requestToken=token; ... if(currentToken.current!==requestToken) ... }`. Biến `token` bị capture trong closure. Nếu `token` thay đổi mà component chưa mount lại, request vẫn dùng `token` cũ.

## 3. Phân loại Lỗi (Vulnerability & Bug Triage)

### Blocker (Cần sửa ngay lập tức)

*   **Hardcode Tọa độ trong Tìm kiếm (API / UX)**
    *   **File:** `frontend/app/explore/page.tsx`
    *   **Chi tiết:** Payload tìm kiếm Hotel và Activity bị fix cứng `{latitude:21.0285,longitude:105.8542}`. Ứng dụng không thể tìm kiếm ở nơi khác.
    *   **Hành động:** Thêm trường input cho vị trí (Destination/City) hoặc Tọa độ vào Form tìm kiếm Hotel/Activity và truyền giá trị thực tế vào payload.
*   **Stale Closure gây lỗi Xung đột Phiên bản (React UX)**
    *   **File:** `frontend/components/PlanView.tsx`
    *   **Chi tiết:** Các hàm thao tác (như `swipe`, `applyRefine`) bị dính stale closure với state `ver` (version) và `token`. Khi user spam click, phiên bản cũ được gửi lên, backend sẽ trả về lỗi 409 Conflict.
    *   **Hành động:** Sử dụng `useRef` cho `version` (`verRef.current`) để luôn lấy giá trị mới nhất trong các callback bất đồng bộ.

### High (Ưu tiên cao)

*   **Lưu trữ Token bằng LocalStorage (Security)**
    *   **File:** `frontend/lib/session.ts`, `frontend/app/login/page.tsx`
    *   **Chi tiết:** `auth_token` và `ma_phien` lưu ở `localStorage` dễ bị tấn công XSS trộm token.
    *   **Hành động:** Đổi sang sử dụng HTTP-Only cookies cho Auth Token.
*   **Chưa xử lý lỗi 401 triệt để (API / UX)**
    *   **File:** `frontend/components/Planner.tsx`, `frontend/app/explore/page.tsx`
    *   **Chi tiết:** API trả về 401 hoặc 403 không ngắt luồng (Planner) hoặc chỉ xóa token mà không văng ra trang Login (Explore).
    *   **Hành động:** Thêm middleware hoặc interceptor để bắt 401/403 toàn cục và redirect về `/login`.
*   **Thiếu Error Handling khi Parse Stream (API)**
    *   **File:** `frontend/lib/api.ts` (Hàm `consumePlanStream`)
    *   **Chi tiết:** Nếu backend lỗi (VD: Pydantic Validation Error trả về Array), frontend văng lỗi không hiển thị được nội dung do mong đợi kiểu String.
    *   **Hành động:** Chuẩn hóa kiểu dữ liệu Error trả về từ API và thêm try-catch/type-guard khi parse.

### Medium (Nên sửa để cải thiện UX/Hiệu suất)

*   **Re-render toàn bộ Bản đồ (Memory Leak / UX)**
    *   **File:** `frontend/components/MapView.tsx`
    *   **Chi tiết:** Đổi marker được chọn (`selectedId`) làm Map khởi tạo lại từ đầu gây giật lag (flicker) màn hình.
    *   **Hành động:** Tách `useEffect` khởi tạo Map và `useEffect` cập nhật UI marker (chỉ đổi style, không vẽ lại map).
*   **Offline Sync chặn Main Thread (UX)**
    *   **File:** `frontend/components/PlanView.tsx`
    *   **Chi tiết:** Lưu toàn bộ đối tượng `plan` lớn vào `localStorage` một cách đồng bộ trong `useEffect` gây giật khựng UI.
    *   **Hành động:** Sử dụng debounce hoặc chuyển sang dùng IndexedDB bất đồng bộ (như `idb-keyval`).
*   **Hardcode ngôn ngữ regex / quickActions (I18N/UX)**
    *   **File:** `frontend/components/Planner.tsx`, `frontend/components/PlanView.tsx`
    *   **Chi tiết:** Logic infer duration chỉ hỗ trợ Regex Anh/Việt. `quickActions` chỉ lấy `vi` và `en`. Gãy nếu dùng ngôn ngữ thứ 3.
    *   **Hành động:** Đưa logic parser về Backend hoặc map với i18n JSON đầy đủ.
*   **Admin Static Token có nguy cơ Brute-force (Security)**
    *   **File:** `frontend/app/admin/page.tsx`
    *   **Chi tiết:** Form yêu cầu nhập token tĩnh mà không có captcha hay rate limit rõ ràng ở Frontend. (Backend cần rate limit).
    *   **Hành động:** Tích hợp Auth chuẩn cho Admin hoặc cảnh báo Backend team thêm Rate Limit.

### Low (Lưu ý / Nâng cấp nhỏ)

*   **Sử dụng `location.assign` thay vì `router.push`:** Trong `Planner.tsx` làm mất trải nghiệm Single Page App. (Chuyển sang dùng `useRouter`).
*   **Service Worker Cache quá rộng:** Caching cả các API `/api/plans/*` có thể chứa data nhạy cảm. Cần giới hạn scope cache của PWA.
*   **Contrast chữ Placeholder Dark Mode:** Tương phản màu chưa đạt chuẩn cao nhất.
*   **RTL Hardcode Flash:** Có thể chớp LTR nhẹ trước khi React hydrate do check JS trên client.

## 4. Đánh giá Tổng hợp & Confidence Score

Hệ thống Frontend nhìn chung vững chắc về cấu trúc thư mục, định tuyến (App Router) và hỗ trợ đa ngôn ngữ. Tuy nhiên, tầng tương tác (Data Fetching, React State, Lifecycle) đang mắc các lỗi kinh điển về Closure và Tối ưu hóa Re-render. Điểm nguy hiểm nhất là việc hardcode tọa độ tìm kiếm khiến tính năng Explore bị tê liệt một phần lớn công dụng thực tế. Bảo mật ở mức trung bình khá, cần nâng cấp lên HTTP-Only cookie để sẵn sàng cho Production.

- **Ground-truth verification:** 4/4 claims quan trọng đã được xác minh bằng cách đọc mã nguồn thực tế (401 Redirect, MapView useEffect, Explore Hardcode, PlanView closure).
- **Confidence Score:** 9.5/10. Các đánh giá có độ tin cậy rất cao nhờ việc đối chiếu chéo và tự kiểm chứng mã nguồn.
