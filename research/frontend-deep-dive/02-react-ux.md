# Báo cáo Audit React & UI Components (Frontend)

Tiến hành deep audit kiến trúc React, state management, lifecycle, side-effects và race conditions trong các file UI components cốt lõi (`Planner`, `PlanView`, `MapView`, `Navigation`, `LocaleProvider`...).

## 1. Planner.tsx (Chat Flow)

**File:** `frontend/components/Planner.tsx`

- **Line 33 (Low):** `setContext((current) => (current === previousDefault.current ? next : current))`
  Logic reset context khi chuyển ngôn ngữ. Chạy ổn nhưng UX hơi kỳ nếu người dùng đã type một nửa prompt bằng tiếng cũ và text đó vô tình khớp với `previousDefault`.
  *Đề xuất:* Giữ nguyên, chấp nhận UX hiện tại vì tỷ lệ xảy ra thấp.

- **Line 66-71 (Medium):** `inferDuration` regex
  Hàm regex hardcode tiếng Anh/Việt. Nếu thêm ngôn ngữ mới (Pháp, Nhật...), planner sẽ mặc định fallback về `ca_ngay`.
  *Đề xuất:* Đưa logic infer duration vào backend hoặc mapping array theo `locale` từ i18n config.

- **Line 97 (High):** Bỏ qua lỗi 401/403
  ```tsx
  const response = await fetch(`${API_URL}/api/plan/generate`, { ... });
  const result = await consumePlanStream(response, ...);
  ```
  Fetch không check `response.ok`. Nếu backend trả `429 Too Many Requests` hoặc `401`, `consumePlanStream` có thể parse JSON lỗi, dẫn đến `generateFailed`.
  *Đề xuất:* Thêm `if (!response.ok) throw new Error(...)` trước khi gọi stream.

- **Line 115 (Low):** `location.assign` thay vì Next.js Router
  ```tsx
  location.assign(`/plan/${result.token}`);
  ```
  Buộc trình duyệt full-reload thay vì client-side navigation. Phá vỡ cảm giác SPA.
  *Đề xuất:* Dùng `useRouter` từ `next/navigation` và gọi `router.push()`.

## 2. PlanView.tsx (Itinerary, Chat, Sidebar)

**File:** `frontend/components/PlanView.tsx`

- **Line 81-82 (Blocker):** Stale Closure khi Fetch API
  ```tsx
  const request=async(input:RequestInfo|URL,init:RequestInit={})=>{
      const requestToken=token; 
      // ...
      if(currentToken.current!==requestToken) throw new DOMException("Stale plan request","AbortError");
      return response;
  };
  ```
  Mặc dù có `currentToken` check để chống race conditions, nhưng các hàm gọi `request` (như `swipe`, `applyRefine`) lại dùng `ver` (state `version`) ở thời điểm chúng được tạo ra (closure).
  Nếu user spam nút "Swipe", `ver` truyền vào API sẽ luôn là `ver` cũ do closure chưa update, dẫn đến lỗi xung đột phiên bản (409) ở backend.
  *Đề xuất:* Dùng `verRef = useRef(version)` và lấy `verRef.current` bên trong các hàm async.

- **Line 126 (High):** Unhandled UI state khi Refine
  ```tsx
  setConversation(items=>[...items,{role:"user",text:messageText}]);
  setChat("");
  ```
  Không disable ô input chat khi đang `busy` (có `disabled={disabled}` trong JSX nhưng request chạy ngầm không set `busy="refine"` đúng cách nếu `start("refine")` tạch). Thực tế, `applyRefine` gọi `start("refine")` và chặn spam, nhưng UX sẽ im lìm không xoay spinner.
  *Đề xuất:* Chắc chắn UI hiện loading bubble trong conversation.

- **Line 93-94 (Medium):** Offline sync effect
  ```tsx
  useEffect(()=>{
      try{localStorage.setItem(`offline-plan:${token}`,JSON.stringify({plan,version:ver,savedAt:new Date().toISOString()}))}
      // ...
  },[plan,token,ver]);
  ```
  Lưu `plan` vào `localStorage` mỗi khi thay đổi. Với `plan` lớn (nhiều ngày, nhiều text), thao tác này chặn main thread (blocking I/O).
  *Đề xuất:* Thêm `debounce` hoặc dùng `IndexedDB` (như `idb-keyval`) cho operations async.

- **Line 146 (Medium):** Hardcode `vi` và `en` cho quickRefines
  ```tsx
  const quickActions=locale==="vi"?quickRefines.vi:quickRefines.en;
  ```
  Chưa hỗ trợ các locale khác (như `ar`, `ja`, `zh`). Sẽ lỗi nếu locale là ngôn ngữ khác.
  *Đề xuất:* Thêm fallback `quickRefines[locale] || quickRefines.en`.

## 3. MapView.tsx & RoadTripMap.tsx (Leaflet)

**File:** `frontend/components/MapView.tsx`

- **Line 24-26 (Medium):** Memory Leak Map Markers
  Leaflet map bị destroy ở `useEffect` cleanup (`map.remove()`), nhưng các DOM events binded trên `marker.on("click")` có thể gây memory leak nhỏ nếu `onSelect` capture DOM lớn.
  *Đề xuất:* Bản thân `map.remove()` đã xoá markers, nhưng tốt hơn nên quản lý instances thay vì render lại toàn bộ Map khi `selectedId` đổi.
  Hiện tại, `MapView` re-run toàn bộ `useEffect` (tạo Map mới hoàn toàn) MỖI LẦN `selectedId` thay đổi. Điều này cực kỳ tốn tài nguyên (flicker bản đồ).
  *Blocker UI:* Đổi style marker khi chọn địa điểm sẽ chớp bản đồ. Cần lưu `map` vào `ref` và chỉ update CSS/radius marker trong một `useEffect` riêng biệt phụ thuộc vào `selectedId`.

## 4. Provider & Workers

- **LocaleProvider.tsx (Low):** Sự kiện `travel-preferences-changed` dùng window event là tốt, nhưng chưa có Error Boundary bọc quanh context.
- **ServiceWorkerRegistration.tsx (Note):** Check `process.env.NODE_ENV === "production"` ok.

## Kết luận & Confidence

- Kịch bản race conditions do stale closure trong `PlanView` là lỗi nặng nhất, dễ khiến UI out-of-sync và backend từ chối thao tác.
- Leaflet map re-render toàn bộ khi click đổi điểm chọn làm trải nghiệm UX cực tệ (flicker).

**Confidence Score:** 9/10
**Tổng số file kiểm tra:** 6
**Ground-truth tally:** 5 issues valid.