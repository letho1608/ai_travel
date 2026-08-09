# Red-team Audit: Frontend

## 1. Synthesis Lỗ hổng (Over-optimism)

*   **UUIDv4 Token URL:** Synthesis bảo an toàn. Sai. URL rò rỉ qua Referer. Lưu trong browser history. Mạng xã hội scrape. Lộ token.
*   **LocalStorage rủi ro High:** Synthesis bảo rủi ro mất token. XSS làm được nhiều hơn. Gọi API trực tiếp. Chặn XSS quan trọng hơn đổi chỗ lưu token.

## 2. Điểm mù (MỚI)

### BLOCKER: SSR Crash Server
*   **File:** `frontend/app/plan/[token]/page.tsx:6`
*   **Lỗi:** `fetch` thiếu timeout.
*   **Hậu quả:** Backend treo, SSR treo. Cạn connection pool. Server sập.
*   **Fix:** Thêm `AbortSignal.timeout()`.

### HIGH: Request Leak
*   **File:** `frontend/components/Planner.tsx:94-98`
*   **Lỗi:** Ghi đè `controllerRef.current` không gọi `.abort()`.
*   **Hậu quả:** Spam click tạo nhiều request ngầm. Lãng phí tài nguyên. Race condition.
*   **Fix:** `controllerRef.current?.abort()` trước khi tạo mới.

### HIGH: Lỗi bắt lỗi API
*   **File:** `frontend/lib/api.ts:16-19`
*   **Lỗi:** `catch` gọi lại `JSON.parse` trên chuỗi gây lỗi ở `try`.
*   **Hậu quả:** Luôn ném `SyntaxError`. Mất thông báo lỗi thực từ backend. UI luôn hiện "Không thể tạo kế hoạch".
*   **Fix:** Bỏ parse lặp. Trả lỗi trực tiếp.

## 3. Honest Confidence Rating

**Điểm: 5.5 / 10**
Synthesis lạc quan. Code thiếu an toàn phân tán. Thiếu timeout. Xử lý lỗi sai. Dễ sập dưới tải. Khắc phục Blocker ngay.