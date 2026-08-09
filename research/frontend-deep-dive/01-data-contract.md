# 01 Data Contract & API Integration Audit (Frontend vs Backend)

## Scope
- lib/api.ts, lib/types.ts, lib/session.ts
- app/page.tsx, app/layout.tsx, app/plan/[token]/page.tsx, app/history/page.tsx, app/explore/page.tsx, app/admin/page.tsx, app/login/page.tsx
- NEXT_PUBLIC_ env, next.config

## Findings

### lib/api.ts
- **File:Line:** `lib/api.ts:24` (consumePlanStream function)
- **Level:** Medium
- **Finding:** Error handling logic throws `parsed.detail ?? text` for non-ok responses. If `parsed.detail` is not a string (e.g. array of validation errors from Pydantic), this might cause rendering issues or uncaught errors in components expecting string errors.
- **Action:** Serialize Pydantic validation errors or ensure backend always returns a string `detail`. Add robust type checking for the error structure in frontend.

### lib/types.ts vs backend schemas
- **File:Line:** `lib/api.ts:46` (Plan type)
- **Level:** High
- **Finding:** Frontend `Plan` type defines `thoi_luong: string;`. Backend `PlanRequest` expects `thoi_luong: Duration` which is `Literal["vai_gio", "nua_ngay", "ca_ngay", "nhieu_ngay"]`. While `Plan` is response type, need to ensure request payload for plan generation matches backend literals. (Wait, `PlanRequest` is for POST /api/planner. Need to check `Planner` component - out of scope for me, but worth noting the data contract).
- **Action:** Ensure types match exactly. Create a shared `types.ts` that accurately reflects the Python Pydantic models (e.g., `Duration`, `Locale`, `HOTEL_AMENITIES`).

### app/plan/[token]/page.tsx
- **File:Line:** `app/plan/[token]/page.tsx:5`
- **Level:** Note
- **Finding:** Server-side fetching `API_URL/api/plans/${token}` using `fetch(..., {cache:"no-store"})`. Correctly uses SSR. Handles 404 via `notFound()`.
- **Action:** None. Looks good.

### app/explore/page.tsx
- **File:Line:** `app/explore/page.tsx:29` (search function)
- **Level:** Blocker
- **Finding:** Flight payload uses `departure_date: departure`. Backend `FlightSearchRequest` validates `departure_date: date` and `return_date: date | None`. But `returnDate` from form might be `""` (empty string) instead of `null`. The code does `return_date: returnDate || null`, which is good. However, `TransferSearchRequest` expects `start_datetime: datetime` (timezone required). Frontend sends `start_datetime: transferStart.toISOString()`, which includes 'Z' (UTC). This should be valid for Pydantic if timezone aware.
- **Action:** Verify Pydantic `datetime` parsing with 'Z'.

- **File:Line:** `app/explore/page.tsx:29` (search function)
- **Level:** High
- **Finding:** Hotel payload uses `latitude: 21.0285, longitude: 105.8542` hardcoded. It ignores the form inputs (if any) or user location.
- **Action:** Use actual location values for Hotel search instead of hardcoded Hanoi coordinates.

- **File:Line:** `app/explore/page.tsx:29` (search function)
- **Level:** High
- **Finding:** Activity payload uses `latitude: 21.0285, longitude: 105.8542` hardcoded. It ignores the form inputs (if any) or user location.
- **Action:** Use actual location values for Activity search instead of hardcoded Hanoi coordinates.

- **File:Line:** `app/explore/page.tsx:32`
- **Level:** Medium
- **Finding:** `response.status === 401` handler inside `requestHelp` clears `localStorage.removeItem("auth_token")`, but does not redirect to login page.
- **Action:** Implement a proper redirect to `/login` when 401 is encountered.

### app/admin/page.tsx
- **File:Line:** `app/admin/page.tsx:90`
- **Level:** Low
- **Finding:** `sessionStorage.setItem("admin_token", token)` and `support_token`. Token handling is manual and basic.
- **Action:** Note for security.

## Data Contract Mapping Table

| Frontend Entity | Path | Backend Schema / Type | Match | Notes |
|---|---|---|---|---|
| FlightSearch | `POST /api/inventory/flights/search` | `FlightSearchRequest` | Yes | `return_date` handles null. |
| HotelSearch | `POST /api/inventory/hotels/search` | `HotelSearchRequest` | Partial | **Latitude/Longitude hardcoded in frontend.** |
| ActivitySearch | `POST /api/inventory/activities/search` | `ActivitySearchRequest` | Partial | **Latitude/Longitude hardcoded in frontend.** |
| TransferSearch | `POST /api/inventory/transfers/search` | `TransferSearchRequest` | Yes | `start_datetime` sends ISO string (UTC). |
| BookingAssistance | `POST /api/inventory/booking-assistance` | `BookingAssistanceRequest` | Yes | Includes auth header. |

## Summary
Audit completed for core data contracts, session flow, and API integration paths. SSR logic in `plan/[token]` is solid. The primary issues lie in the `Explore` component, where `HotelSearch` and `ActivitySearch` hardcode latitude and longitude to Hanoi, ignoring potential user input or dynamic context. Error handling in stream parsing `consumePlanStream` needs resilience against array-based validation errors from Pydantic. 401 Unauthorized handling in `Explore` clears the token but fails to redirect the user to the login flow.

Confidence Score: 8/10. Verify Pydantic datetime parsing and Planner component request shapes for higher confidence.