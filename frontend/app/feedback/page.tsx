"use client";

import { FormEvent, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useLocale } from "@/components/LocaleProvider";

type Review = {
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

const CATEGORY_LABELS: Record<string, string> = {
  trai_nghiem: "Trải nghiệm AI",
  tinh_nang: "Đề xuất tính năng",
  dia_diem: "Đóng góp địa điểm",
  khac: "Góp ý khác",
};

export default function FeedbackPage() {
  const { t } = useLocale();
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [rating, setRating] = useState(5);
  const [category, setCategory] = useState("trai_nghiem");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [averageRating, setAverageRating] = useState(5.0);
  const [filterCategory, setFilterCategory] = useState("all");
  const [loadingReviews, setLoadingReviews] = useState(true);

  function getSessionId(): string {
    if (typeof window === "undefined") return "default-session";
    let stored = localStorage.getItem("ma_phien");
    if (!stored || !/^[0-9a-f-]{36}$/i.test(stored)) {
      stored = crypto.randomUUID();
      localStorage.setItem("ma_phien", stored);
    }
    return stored;
  }

  async function loadReviews() {
    try {
      setLoadingReviews(true);
      const res = await fetch(`${API_URL}/api/feedback`);
      if (res.ok) {
        const data = await res.json();
        setReviews(data.reviews || []);
        if (typeof data.average_rating === "number") {
          setAverageRating(data.average_rating);
        }
      }
    } catch {
      // Fallback gracefully
    } finally {
      setLoadingReviews(false);
    }
  }

  useEffect(() => {
    loadReviews();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    setBusy(true);
    setMessage(null);

    const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      const res = await fetch(`${API_URL}/api/feedback`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          name: name.trim() || "Du khách",
          contact: contact.trim() || "N/A",
          rating,
          category,
          title: title.trim() || "Đánh giá dịch vụ",
          content: content.trim(),
          ma_phien: getSessionId(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Không thể gửi đánh giá.");

      setMessage({ text: "Cảm ơn bạn đã gửi đánh giá và đóng góp quý báu cho cộng đồng!", type: "success" });
      setTitle("");
      setContent("");
      loadReviews();
    } catch (err: any) {
      setMessage({ text: err.message || "Có lỗi xảy ra khi gửi góp ý.", type: "error" });
    } finally {
      setBusy(false);
    }
  }

  const visibleReviews = filterCategory === "all"
    ? reviews
    : reviews.filter((r) => r.category === filterCategory);

  return (
    <div className="feedback-page shell" style={{ padding: "32px 0 64px" }}>
      <header className="section-head" style={{ maxWidth: "800px", margin: "0 auto 36px", textAlign: "center" }}>
        <span className="eyebrow" style={{ display: "inline-block", padding: "6px 14px", borderRadius: "999px", background: "var(--lavender-soft)", color: "var(--ink-3)", fontWeight: 800, fontSize: "13px", marginBottom: "12px" }}>
          Cộng đồng du lịch
        </span>
        <h1 style={{ fontSize: "clamp(32px, 4.5vw, 52px)", letterSpacing: "-0.035em", margin: "8px 0 14px" }}>
          Đánh giá & Góp ý trải nghiệm
        </h1>
        <p style={{ color: "var(--muted)", fontSize: "17px", lineHeight: 1.6, maxWidth: "620px", margin: "0 auto" }}>
          Ý kiến của bạn là động lực để chúng tôi hoàn thiện sản phẩm mỗi ngày. Hãy chia sẻ cảm nhận hoặc đề xuất tính năng bạn mong muốn.
        </p>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 480px) 1fr", gap: "36px", alignItems: "start" }}>
        {/* Form Gửi Đánh Giá */}
        <section className="card" style={{ padding: "32px", borderRadius: "var(--radius-xl)", background: "var(--surface)", border: "1px solid var(--line)", boxShadow: "var(--shadow-lg)" }}>
          <h2 style={{ fontSize: "22px", margin: "0 0 8px" }}>Gửi ý kiến đóng góp</h2>
          <p style={{ color: "var(--muted)", fontSize: "14px", margin: "0 0 20px" }}>
            Đóng góp trực tiếp tới đội ngũ phát triển Mình Đi Đâu Thế.
          </p>

          <form onSubmit={handleSubmit} style={{ display: "grid", gap: "16px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 700, marginBottom: "6px", color: "var(--ink-2)" }}>
                  Họ và tên *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ví dụ: Hoàng Nam"
                  style={{ width: "100%", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 700, marginBottom: "6px", color: "var(--ink-2)" }}>
                  Email hoặc SĐT *
                </label>
                <input
                  type="text"
                  required
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  placeholder="email@example.com / 09xx"
                  style={{ width: "100%", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 700, marginBottom: "8px", color: "var(--ink-2)" }}>
                Mức độ hài lòng của bạn
              </label>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setRating(star)}
                    style={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      fontSize: "28px",
                      lineHeight: 1,
                      color: star <= rating ? "#f59e0b" : "var(--line-2)",
                      transition: "transform 0.15s ease",
                      padding: "2px",
                    }}
                    aria-label={`${star} sao`}
                  >
                    ★
                  </button>
                ))}
                <span style={{ fontSize: "14px", fontWeight: 700, marginLeft: "8px", color: "var(--ink-2)" }}>
                  {rating === 5 ? "Tuyệt vời (5/5)" : rating === 4 ? "Hài lòng (4/5)" : rating === 3 ? "Bình thường (3/5)" : "Cần cải thiện"}
                </span>
              </div>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 700, marginBottom: "6px", color: "var(--ink-2)" }}>
                Danh mục góp ý
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                style={{ width: "100%", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
              >
                <option value="trai_nghiem">Trải nghiệm lên lịch trình AI</option>
                <option value="tinh_nang">Đề xuất tính năng mới</option>
                <option value="dia_diem">Đóng góp địa điểm / giá cả</option>
                <option value="khac">Góp ý khác</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 700, marginBottom: "6px", color: "var(--ink-2)" }}>
                Tiêu đề ngắn gọn
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ví dụ: AI gợi ý quán bún chả rất ngon!"
                style={{ width: "100%", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 700, marginBottom: "6px", color: "var(--ink-2)" }}>
                Nội dung chi tiết *
              </label>
              <textarea
                required
                rows={4}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Chia sẻ chi tiết trải nghiệm, điểm bạn thích hoặc những điểm chúng tôi cần khắc phục..."
                style={{ width: "100%", padding: "12px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", background: "var(--surface-2)", color: "var(--ink)", resize: "vertical" }}
              />
            </div>

            {message && (
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: "var(--radius-sm)",
                  background: message.type === "success" ? "var(--green-soft)" : "var(--danger-soft)",
                  color: message.type === "success" ? "var(--brand)" : "var(--danger)",
                  fontSize: "14px",
                  fontWeight: 600,
                }}
              >
                {message.text}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="primary"
              style={{
                width: "100%",
                minHeight: "48px",
                borderRadius: "var(--radius-full)",
                fontWeight: 800,
                fontSize: "15px",
                cursor: busy ? "not-allowed" : "pointer",
                marginTop: "4px",
              }}
            >
              {busy ? "Đang gửi góp ý..." : "Gửi đánh giá & Góp ý"}
            </button>
          </form>
        </section>

        {/* Danh Sách Đánh Giá Cộng Đồng */}
        <section>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <h2 style={{ fontSize: "24px", margin: 0 }}>Đánh giá từ cộng đồng</h2>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                <span style={{ color: "#f59e0b", fontSize: "18px" }}>★</span>
                <strong style={{ fontSize: "16px" }}>{averageRating} / 5.0</strong>
                <span style={{ color: "var(--muted)", fontSize: "13px" }}>({reviews.length} đánh giá)</span>
              </div>
            </div>

            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
              {["all", "trai_nghiem", "tinh_nang", "dia_diem"].map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setFilterCategory(cat)}
                  style={{
                    padding: "6px 12px",
                    borderRadius: "var(--radius-full)",
                    border: "1px solid var(--line-2)",
                    background: filterCategory === cat ? "var(--brand)" : "var(--surface)",
                    color: filterCategory === cat ? "var(--brand-contrast)" : "var(--ink-2)",
                    fontSize: "12.5px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  {cat === "all" ? "Tất cả" : CATEGORY_LABELS[cat] || cat}
                </button>
              ))}
            </div>
          </div>

          {loadingReviews ? (
            <p style={{ color: "var(--muted)", fontStyle: "italic" }}>Đang tải đánh giá...</p>
          ) : visibleReviews.length === 0 ? (
            <div className="card" style={{ padding: "40px 20px", textAlign: "center", background: "var(--surface)", borderRadius: "var(--radius-lg)" }}>
              <p style={{ color: "var(--muted)", margin: 0 }}>Chưa có đánh giá nào trong danh mục này.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gap: "16px" }}>
              {visibleReviews.map((rev) => (
                <article
                  key={rev.id}
                  className="card"
                  style={{
                    padding: "20px 24px",
                    borderRadius: "var(--radius-lg)",
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px", marginBottom: "10px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <strong style={{ fontSize: "16px", color: "var(--ink)" }}>{rev.name}</strong>
                        <span
                          style={{
                            fontSize: "11.5px",
                            padding: "3px 8px",
                            borderRadius: "999px",
                            background: "var(--lavender-soft)",
                            color: "var(--ink-3)",
                            fontWeight: 700,
                          }}
                        >
                          {CATEGORY_LABELS[rev.category] || rev.category}
                        </span>
                      </div>
                      <div style={{ color: "#f59e0b", fontSize: "14px", marginTop: "3px" }}>
                        {"★".repeat(rev.rating)}
                        {"☆".repeat(5 - rev.rating)}
                      </div>
                    </div>
                    <time style={{ fontSize: "12px", color: "var(--muted-2)", whiteSpace: "nowrap" }}>
                      {new Date(rev.created_at).toLocaleDateString("vi-VN")}
                    </time>
                  </div>

                  <h3 style={{ fontSize: "16px", margin: "0 0 6px", fontWeight: 700 }}>{rev.title}</h3>
                  <p style={{ color: "var(--muted)", fontSize: "14.5px", lineHeight: 1.6, margin: 0 }}>{rev.content}</p>

                  {rev.admin_reply && (
                    <div
                      style={{
                        marginTop: "12px",
                        padding: "10px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--lavender-50)",
                        borderLeft: "3px solid var(--brand)",
                      }}
                    >
                      <strong style={{ display: "block", fontSize: "12.5px", color: "var(--brand)", marginBottom: "3px" }}>
                        Phản hồi từ Ban quản trị Mình Đi Đâu Thế:
                      </strong>
                      <p style={{ margin: 0, fontSize: "13.5px", color: "var(--ink-2)" }}>{rev.admin_reply}</p>
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
