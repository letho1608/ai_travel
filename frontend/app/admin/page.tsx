"use client";

import { FormEvent, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

type BookingRequest = {
  id: string;
  offer_id: string;
  trang_thai: string;
  ngay_tao: string;
  ghi_chu?: string | null;
  loai?: string | null;
  provider_reference?: string | null;
};

type ProviderStatus = {
  name: string;
  mode: string;
  status: string;
  detail: string;
};

type ProviderDiagnostic = {
  provider: string;
  ready: boolean;
  mode?: string;
  model?: string;
  base_url?: string;
  required_env: string[];
  next_action: string;
  circuit_breaker?: {
    state: string;
    recent_failures: number;
    remaining_open_seconds: number;
  };
};

type DataQuality = {
  place_count: number;
  unusual_hours: number;
  source_url_coverage_percent: number;
  missing_source_url: number;
  distance_matrix: {
    loaded: boolean;
    profile?: string;
    cell_count?: number;
  };
  sample_places: Array<{
    id: string;
    name: string;
    kind: string;
    area: string;
    open_hour: number;
    close_hour: number;
    source_url?: string | null;
  }>;
  kind_counts: Record<string, number>;
  top_tags: Record<string, number>;
  failing_coverage: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
};

type AdminUser = {
  id: string;
  email: string;
  name?: string | null;
  provider?: string | null;
  created_at?: string | null;
  plans: number;
  comments: number;
  booking_requests: number;
  feedback: number;
  notifications: number;
};

type AdminFeedback = {
  id: string;
  name: string;
  contact: string;
  rating: number;
  category: string;
  title: string;
  content: string;
  status: string;
  admin_reply?: string | null;
  created_at: string;
};

type AdminData = {
  environment: string;
  ready: boolean;
  summary: {
    plans: number;
    comments: number;
    user_reviews?: number;
    booking_requests: number;
    open_booking_requests: number;
    ai_calls: number;
    daily_ai_cost_usd: number;
  };
  limits: Record<string, number>;
  providers: ProviderStatus[];
  provider_diagnostics: Record<string, ProviderDiagnostic>;
  ai_quality: {
    mode: string;
    model: string;
    live_provider_ready: boolean;
    daily_ai_cost_usd: number;
    total_plans: number;
    deterministic_plan_count: number;
    deterministic_rate_percent: number;
    fallback_plan_count: number;
    next_action: string;
  };
  catalog_quality: DataQuality;
  user_reviews?: AdminFeedback[];
  booking_requests: BookingRequest[];
  recent_events: Array<{
    thoi_gian: string;
    ma_phien: string;
    su_kien: string;
    du_lieu: Record<string, unknown>;
  }>;
};

const STATUS_LABELS: Record<string, string> = {
  new: "Mới nhận",
  reviewed: "Đã xem",
  resolved: "Đã phản hồi",
  hidden: "Ẩn",
};

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [data, setData] = useState<AdminData | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [lastLoaded, setLastLoaded] = useState<Date | null>(null);

  // Reviews / Feedback state
  const [reviews, setReviews] = useState<AdminFeedback[]>([]);
  const [reviewFilter, setReviewFilter] = useState("all");
  const [reviewReplies, setReviewReplies] = useState<Record<string, string>>({});
  const [reviewBusyId, setReviewBusyId] = useState<string | null>(null);

  // Diagnostics & maintenance
  const [diagnosticsBusy, setDiagnosticsBusy] = useState(false);
  const [maintenanceBusy, setMaintenanceBusy] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState("");

  function getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {};
    if (token.trim()) {
      headers["X-Admin-Token"] = token.trim();
    }
    const userAuth = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    if (userAuth) {
      headers["Authorization"] = `Bearer ${userAuth}`;
    }
    return headers;
  }

  async function loadDashboard(overrideToken?: string) {
    setBusy(true);
    setError("");
    const tok = overrideToken ?? token;
    if (tok.trim()) {
      sessionStorage.setItem("admin_token", tok.trim());
    }
    try {
      const headers: Record<string, string> = {};
      if (tok.trim()) headers["X-Admin-Token"] = tok.trim();
      const userAuth = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
      if (userAuth) headers["Authorization"] = `Bearer ${userAuth}`;

      const res = await fetch(`${API_URL}/api/admin/dashboard`, { headers });
      const payload = await res.json();
      if (!res.ok) {
        if (res.status === 403) {
          throw new Error("Tài khoản của bạn là người dùng thông thường (User). Hãy đăng nhập tài khoản admin hoặc nhập Secret Admin Token bên dưới.");
        }
        if (res.status === 401) {
          throw new Error("Admin Token không chính xác. (Mẹo local test: 'local-support-demo')");
        }
        throw new Error(payload.detail || "Không tải được dữ liệu admin.");
      }
      setData(payload);
      setReviews(payload.user_reviews || []);
      setLastLoaded(new Date());
    } catch (err: any) {
      setError(err.message || "Không tải được dashboard.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const storedToken = sessionStorage.getItem("admin_token") || "";
    const role = localStorage.getItem("user_role");
    const authToken = localStorage.getItem("auth_token");
    setUserRole(role);
    if (storedToken) setToken(storedToken);

    // Auto-load if user is logged in as admin or has token
    if (role === "admin" || (authToken && role === "admin") || storedToken) {
      void loadDashboard(storedToken);
    }
  }, []);

  async function handleUpdateReview(reviewId: string, status: string) {
    setReviewBusyId(reviewId);
    try {
      const replyText = reviewReplies[reviewId];
      const res = await fetch(`${API_URL}/api/feedback/${reviewId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({
          status,
          admin_reply: replyText !== undefined ? replyText.trim() : null,
        }),
      });
      const updated = await res.json();
      if (!res.ok) throw new Error(updated.detail || "Không cập nhật được đánh giá.");

      setReviews((prev) => prev.map((r) => (r.id === reviewId ? { ...r, status, admin_reply: replyText || r.admin_reply } : r)));
    } catch (err: any) {
      alert(err.message || "Có lỗi xảy ra khi cập nhật đánh giá.");
    } finally {
      setReviewBusyId(null);
    }
  }

  async function refreshDiagnostics() {
    if (!data) return;
    setDiagnosticsBusy(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/providers/diagnostics`, { headers: getAuthHeaders() });
      const payload = await res.json();
      if (res.ok) setData((curr) => (curr ? { ...curr, provider_diagnostics: payload } : curr));
    } catch {
      // Ignored
    } finally {
      setDiagnosticsBusy(false);
    }
  }

  async function cleanupExpired() {
    setMaintenanceBusy(true);
    setMaintenanceMessage("");
    try {
      const res = await fetch(`${API_URL}/api/admin/maintenance/cleanup-expired`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const payload = await res.json();
      if (res.ok) {
        setMaintenanceMessage(`Đã dọn dẹp thành công ${payload.removed_plans || 0} kế hoạch hết hạn.`);
        void loadDashboard();
      }
    } catch {
      setMaintenanceMessage("Không thể chạy cleanup.");
    } finally {
      setMaintenanceBusy(false);
    }
  }

  const visibleReviews = reviewFilter === "all"
    ? reviews
    : reviews.filter((r) => r.status === reviewFilter);

  return (
    <main className="admin-page shell" style={{ padding: "32px 0 64px" }}>
      <header className="section-head" style={{ marginBottom: "28px" }}>
        <span className="eyebrow" style={{ display: "inline-block", padding: "6px 14px", borderRadius: "999px", background: "var(--lavender-soft)", color: "var(--ink-3)", fontWeight: 800, fontSize: "13px", marginBottom: "8px" }}>
          Bảng điều khiển Quản trị
        </span>
        <h1 style={{ fontSize: "clamp(28px, 4vw, 42px)", margin: "4px 0 8px" }}>Quản trị hệ thống & Đánh giá</h1>
        <p style={{ color: "var(--muted)", fontSize: "16px", margin: 0 }}>
          Theo dõi trạng thái AI, kho dữ liệu địa điểm, hiệu suất hệ thống và phản hồi ý kiến từ người dùng.
        </p>
      </header>

      {/* Role & Auth Status Bar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px", marginBottom: "24px", padding: "14px 20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--line)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 14px",
              borderRadius: "999px",
              fontSize: "13px",
              fontWeight: 800,
              background: userRole === "admin" ? "var(--green-soft)" : "var(--lavender-soft)",
              color: userRole === "admin" ? "var(--brand)" : "var(--ink-2)",
            }}
          >
            {userRole === "admin" ? "🟢 Quản trị viên (Admin)" : "👤 Người dùng (User)"}
          </span>
          {lastLoaded && (
            <span style={{ fontSize: "12.5px", color: "var(--muted)" }}>
              Cập nhật lúc: {lastLoaded.toLocaleTimeString("vi-VN")}
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {data && (
            <button
              type="button"
              className="secondary"
              onClick={() => loadDashboard()}
              disabled={busy}
              style={{ padding: "8px 16px", borderRadius: "var(--radius-full)", fontSize: "13px", fontWeight: 700 }}
            >
              {busy ? "Đang tải lại..." : "Tải lại dữ liệu"}
            </button>
          )}
        </div>
      </div>

      {/* Token Box (Only if not already authenticated or if error) */}
      {(!data || userRole !== "admin") && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            void loadDashboard();
          }}
          style={{ padding: "24px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--line)", marginBottom: "28px" }}
        >
          <h3 style={{ fontSize: "17px", margin: "0 0 8px" }}>Xác thực Secret Admin Token</h3>
          <p style={{ color: "var(--muted)", fontSize: "13.5px", margin: "0 0 16px" }}>
            Nhập token quản trị hoặc đăng nhập tài khoản admin để mở toàn bộ quyền truy cập. (Mẹo local test: <code>local-support-demo</code>)
          </p>
          <div style={{ display: "flex", gap: "10px", maxWidth: "560px" }}>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Nhập secret admin token..."
              style={{ flex: 1, padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
            />
            <button type="submit" className="primary" disabled={busy} style={{ padding: "10px 20px", borderRadius: "var(--radius-sm)", fontWeight: 700 }}>
              {busy ? "Đang xác thực..." : "Mở Dashboard"}
            </button>
          </div>
        </form>
      )}

      {error && (
        <div style={{ padding: "14px 18px", borderRadius: "var(--radius-md)", background: "var(--danger-soft)", color: "var(--danger)", marginBottom: "24px", fontWeight: 600, fontSize: "14px" }}>
          {error}
        </div>
      )}

      {data && (
        <div style={{ display: "grid", gap: "32px" }}>
          {/* System Metrics Strip */}
          <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
            <article className="card" style={{ padding: "20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--line)" }}>
              <span style={{ fontSize: "13px", color: "var(--muted)" }}>Môi trường</span>
              <h3 style={{ fontSize: "24px", margin: "6px 0 2px" }}>{data.environment}</h3>
              <small style={{ color: data.ready ? "var(--brand)" : "var(--danger)", fontWeight: 700 }}>{data.ready ? "Sẵn sàng (Ready)" : "Cần kiểm tra"}</small>
            </article>

            <article className="card" style={{ padding: "20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--line)" }}>
              <span style={{ fontSize: "13px", color: "var(--muted)" }}>Tổng số kế hoạch</span>
              <h3 style={{ fontSize: "24px", margin: "6px 0 2px" }}>{data.summary.plans}</h3>
              <small style={{ color: "var(--muted)" }}>{data.summary.comments} bình luận</small>
            </article>

            <article className="card" style={{ padding: "20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--line)" }}>
              <span style={{ fontSize: "13px", color: "var(--muted)" }}>Chi phí AI hôm nay</span>
              <h3 style={{ fontSize: "24px", margin: "6px 0 2px" }}>${data.summary.daily_ai_cost_usd.toFixed(4)}</h3>
              <small style={{ color: "var(--muted)" }}>{data.summary.ai_calls} lượt gọi AI</small>
            </article>

            <article className="card" style={{ padding: "20px", borderRadius: "var(--radius-lg)", background: "var(--surface)", border: "1px solid var(--line)" }}>
              <span style={{ fontSize: "13px", color: "var(--muted)" }}>Đánh giá người dùng</span>
              <h3 style={{ fontSize: "24px", margin: "6px 0 2px" }}>{reviews.length}</h3>
              <small style={{ color: "var(--brand)", fontWeight: 700 }}>{reviews.filter((r) => r.status === "new").length} đánh giá mới</small>
            </article>
          </section>

          {/* User Reviews & Feedback Management */}
          <section className="card" style={{ padding: "28px", borderRadius: "var(--radius-xl)", background: "var(--surface)", border: "1px solid var(--line)", boxShadow: "var(--shadow-sm)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "12px" }}>
              <div>
                <h2 style={{ fontSize: "22px", margin: "0 0 4px" }}>Quản lý Đánh giá & Góp ý người dùng</h2>
                <p style={{ color: "var(--muted)", fontSize: "14px", margin: 0 }}>
                  Xem và phản hồi trực tiếp tới đánh giá của khách hàng từ trang Góp ý.
                </p>
              </div>

              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {["all", "new", "reviewed", "resolved"].map((st) => (
                  <button
                    key={st}
                    type="button"
                    onClick={() => setReviewFilter(st)}
                    style={{
                      padding: "6px 14px",
                      borderRadius: "var(--radius-full)",
                      border: "1px solid var(--line-2)",
                      background: reviewFilter === st ? "var(--brand)" : "var(--surface)",
                      color: reviewFilter === st ? "var(--brand-contrast)" : "var(--ink-2)",
                      fontSize: "12.5px",
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {st === "all" ? "Tất cả" : STATUS_LABELS[st] || st}
                  </button>
                ))}
              </div>
            </div>

            {visibleReviews.length === 0 ? (
              <p style={{ color: "var(--muted)", fontStyle: "italic", margin: "20px 0" }}>
                Không có đánh giá nào phù hợp với bộ lọc hiện tại.
              </p>
            ) : (
              <div style={{ display: "grid", gap: "16px" }}>
                {visibleReviews.map((rev) => (
                  <article
                    key={rev.id}
                    style={{
                      padding: "20px",
                      borderRadius: "var(--radius-lg)",
                      background: "var(--surface-2)",
                      border: "1px solid var(--line)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px", marginBottom: "10px" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <strong style={{ fontSize: "16px" }}>{rev.name}</strong>
                          <span style={{ fontSize: "13px", color: "var(--muted)" }}>({rev.contact})</span>
                          <span
                            style={{
                              fontSize: "11.5px",
                              padding: "2px 8px",
                              borderRadius: "999px",
                              background: rev.status === "new" ? "var(--lavender-soft)" : rev.status === "resolved" ? "var(--green-soft)" : "var(--surface)",
                              color: rev.status === "new" ? "var(--ink-3)" : rev.status === "resolved" ? "var(--brand)" : "var(--ink-2)",
                              fontWeight: 700,
                            }}
                          >
                            {STATUS_LABELS[rev.status] || rev.status}
                          </span>
                        </div>
                        <div style={{ color: "#f59e0b", fontSize: "14px", marginTop: "3px" }}>
                          {"★".repeat(rev.rating)}
                          {"☆".repeat(5 - rev.rating)}
                        </div>
                      </div>
                      <time style={{ fontSize: "12px", color: "var(--muted)" }}>
                        {new Date(rev.created_at).toLocaleString("vi-VN")}
                      </time>
                    </div>

                    <h4 style={{ fontSize: "16px", margin: "0 0 6px", fontWeight: 700 }}>{rev.title}</h4>
                    <p style={{ color: "var(--ink-2)", fontSize: "14.5px", lineHeight: 1.6, margin: "0 0 14px" }}>{rev.content}</p>

                    {/* Admin Reply & Action */}
                    <div style={{ borderTop: "1px solid var(--line)", paddingTop: "12px", display: "grid", gap: "10px" }}>
                      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                        <input
                          type="text"
                          value={reviewReplies[rev.id] !== undefined ? reviewReplies[rev.id] : rev.admin_reply || ""}
                          onChange={(e) => setReviewReplies({ ...reviewReplies, [rev.id]: e.target.value })}
                          placeholder="Nhập nội dung phản hồi từ Ban quản trị..."
                          style={{ flex: 1, padding: "8px 12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface)", fontSize: "13.5px", color: "var(--ink)" }}
                        />
                        <button
                          type="button"
                          className="primary"
                          disabled={reviewBusyId === rev.id}
                          onClick={() => handleUpdateReview(rev.id, "resolved")}
                          style={{ padding: "8px 16px", borderRadius: "var(--radius-sm)", fontSize: "13px", fontWeight: 700, whiteSpace: "nowrap" }}
                        >
                          {reviewBusyId === rev.id ? "Đang lưu..." : "Phản hồi & Đóng"}
                        </button>
                      </div>

                      <div style={{ display: "flex", gap: "8px" }}>
                        {rev.status !== "reviewed" && rev.status !== "resolved" && (
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => handleUpdateReview(rev.id, "reviewed")}
                            style={{ padding: "4px 10px", fontSize: "12px", borderRadius: "var(--radius-sm)" }}
                          >
                            Đánh dấu Đã xem
                          </button>
                        )}
                        {rev.status !== "hidden" && (
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => handleUpdateReview(rev.id, "hidden")}
                            style={{ padding: "4px 10px", fontSize: "12px", borderRadius: "var(--radius-sm)", color: "var(--danger)" }}
                          >
                            Ẩn đánh giá
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* Provider Readiness & Diagnostics */}
          <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
            <div className="card" style={{ padding: "24px", borderRadius: "var(--radius-xl)", background: "var(--surface)", border: "1px solid var(--line)" }}>
              <h3 style={{ fontSize: "18px", margin: "0 0 16px" }}>Trạng thái AI Providers</h3>
              <div style={{ display: "grid", gap: "12px" }}>
                {data.providers.map((p) => (
                  <article key={p.name} style={{ padding: "12px", borderRadius: "var(--radius-md)", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong>{p.name}</strong>
                      <span className={`admin-pill ${p.status}`}>{p.status}</span>
                    </div>
                    <p style={{ margin: "6px 0 0", fontSize: "13px", color: "var(--muted)" }}>{p.detail}</p>
                  </article>
                ))}
              </div>
            </div>

            <div className="card" style={{ padding: "24px", borderRadius: "var(--radius-xl)", background: "var(--surface)", border: "1px solid var(--line)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "18px", margin: 0 }}>Chẩn đoán AI Provider</h3>
                <button type="button" className="secondary" onClick={refreshDiagnostics} disabled={diagnosticsBusy} style={{ fontSize: "12px", padding: "4px 10px" }}>
                  {diagnosticsBusy ? "Đang kiểm tra..." : "Kiểm tra lại"}
                </button>
              </div>
              <div style={{ display: "grid", gap: "12px" }}>
                {Object.entries(data.provider_diagnostics).map(([key, item]) => (
                  <article key={key} style={{ padding: "12px", borderRadius: "var(--radius-md)", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong>{key.toUpperCase()}</strong>
                      <span className={`admin-pill ${item.ready ? "ready" : "missing_credentials"}`}>{item.ready ? "Sẵn sàng" : "Chưa cấu hình key"}</span>
                    </div>
                    <p style={{ margin: "6px 0 0", fontSize: "13px", color: "var(--muted)" }}>{item.next_action}</p>
                  </article>
                ))}
              </div>
            </div>
          </section>

          {/* System Maintenance */}
          <section className="card" style={{ padding: "24px", borderRadius: "var(--radius-xl)", background: "var(--surface)", border: "1px solid var(--line)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
              <div>
                <h3 style={{ fontSize: "18px", margin: "0 0 6px" }}>Bảo trì & Dọn dẹp dữ liệu</h3>
                <p style={{ color: "var(--muted)", fontSize: "13.5px", margin: 0 }}>
                  Dọn dẹp các lịch trình ẩn danh tạm thời đã quá hạn 30 ngày để tối ưu bộ nhớ.
                </p>
                {maintenanceMessage && <p style={{ color: "var(--brand)", fontSize: "13.5px", fontWeight: 700, margin: "6px 0 0" }}>{maintenanceMessage}</p>}
              </div>
              <button type="button" className="secondary" onClick={cleanupExpired} disabled={maintenanceBusy} style={{ padding: "8px 16px", borderRadius: "var(--radius-full)", fontSize: "13.5px", fontWeight: 700 }}>
                {maintenanceBusy ? "Đang dọn dẹp..." : "Dọn dẹp kế hoạch hết hạn"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
