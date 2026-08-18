"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Planner, { focusPlanner, promptPlanner } from "@/components/Planner";
import { API_URL } from "@/lib/api";
import { useLocale } from "@/components/LocaleProvider";

type Review = {
  id: string;
  name: string;
  rating: number;
  category: string;
  title: string;
  content: string;
};

const curatedDestinations = [
  {
    name: "Đà Nẵng & Hội An",
    tag: "Biển Mỹ Khê · Phố cổ · Bà Nà Hills",
    prompt: "Lịch trình du lịch Đà Nẵng Hội An 3 ngày 2 đêm cho 2 người thích biển và chụp ảnh",
    badge: "Phổ biến nhất",
    image: "https://images.unsplash.com/photo-1559592413-7cec4d0cae2b?w=800&auto=format&fit=crop&q=80",
    fallbackGradient: "linear-gradient(135deg, #0284c7, #0d9488)",
  },
  {
    name: "Hà Nội 36 Phố Phường",
    tag: "Ẩm thực phố cổ · Hồ Gươm · Di sản văn hóa",
    prompt: "Lịch trình food tour và khám phá phố cổ Hà Nội 2 ngày 1 đêm",
    badge: "Đặc sắc",
    image: "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=800&auto=format&fit=crop&q=80",
    fallbackGradient: "linear-gradient(135deg, #d97706, #b45309)",
  },
  {
    name: "Phú Quốc Đảo Ngọc",
    tag: "Hoàng hôn Bãi Trường · Lặn san hô · Hải sản",
    prompt: "Lịch trình nghỉ dưỡng Phú Quốc 4 ngày 3 đêm cho gia đình",
    badge: "Nghỉ dưỡng",
    image: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&auto=format&fit=crop&q=80",
    fallbackGradient: "linear-gradient(135deg, #059669, #0284c7)",
  },
  {
    name: "Sa Pa & Fansipan",
    tag: "Đỉnh Fansipan · Bản Cát Cát · Săn mây",
    prompt: "Lịch trình du lịch Sa Pa 3 ngày 2 đêm săn mây và trekking bản làng",
    badge: "Trekking & Chill",
    image: "https://images.unsplash.com/photo-1570789210967-2cac24afeb00?w=800&auto=format&fit=crop&q=80",
    fallbackGradient: "linear-gradient(135deg, #4f46e5, #059669)",
  },
  {
    name: "Tràng An - Ninh Bình",
    tag: "Di sản thế giới · Tam Cốc · Hang Múa",
    prompt: "Lịch trình khám phá Ninh Bình Tràng An Hang Múa 2 ngày 1 đêm",
    badge: "Di sản UNESCO",
    image: "https://images.unsplash.com/photo-1528127269322-539801943592?w=800&auto=format&fit=crop&q=80",
    fallbackGradient: "linear-gradient(135deg, #0891b2, #15803d)",
  },
  {
    name: "Đà Lạt Mộng Mơ",
    tag: "Cà phê săn mây · Đồi thông · Thời tiết se lạnh",
    prompt: "Lịch trình săn mây và check-in các quán cà phê đẹp ở Đà Lạt 3 ngày",
    badge: "Thời tiết mát mẻ",
    image: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=800&auto=format&fit=crop&q=80",
    fallbackGradient: "linear-gradient(135deg, #ec4899, #8b5cf6)",
  },
];

const highlights = [
  {
    title: "Lập kế hoạch trong 5 giây",
    desc: "AI tự động phân tích ý tưởng, chọn lọc địa điểm thực tế và sắp xếp thời gian hợp lý cho từng ngày.",
    icon: "⚡",
    badge: "Tốc độ cao",
  },
  {
    title: "Tối ưu lộ trình OSRM thật",
    desc: "Đo chuẩn xác cự ly và thời gian di chuyển giữa các điểm đến bằng dữ liệu giao thông OpenStreetMap.",
    icon: "🗺️",
    badge: "Bản đồ thật",
  },
  {
    title: "Minh bạch chi phí dự toán",
    desc: "Dự toán chi phí vé tham quan, ăn uống và đi lại chi tiết theo số lượng người trong đoàn.",
    icon: "💵",
    badge: "Dự toán chuẩn",
  },
  {
    title: "Tùy biến linh hoạt bằng AI",
    desc: "Dễ dàng trò chuyện để đổi quán ăn, đổi điểm tham quan hoặc tùy chỉnh timeline chỉ với 1 thao tác.",
    icon: "🔄",
    badge: "Linh hoạt",
  },
];

const steps = [
  {
    step: "01",
    title: "Mô tả mong muốn",
    desc: "Nhập điểm đến, số ngày, sở thích hoặc chọn gợi ý có sẵn (*Đà Nẵng 3N2Đ, Food tour Hà Nội...*).",
  },
  {
    step: "02",
    title: "AI thiết kế lộ trình",
    desc: "Xem timeline chi tiết từng giờ, bản đồ đường đi tương tác và dự toán chi phí trọn gói.",
  },
  {
    step: "03",
    title: "Trải nghiệm & Xuất file",
    desc: "Đổi điểm đến theo ý thích, xuất file PDF in ra hoặc đồng bộ thẳng vào Google Calendar trên điện thoại.",
  },
];

const fallbackReviews: Review[] = [
  {
    id: "f1",
    name: "Hoàng Nam",
    rating: 5,
    category: "Trải nghiệm AI",
    title: "Lên lịch trình Đà Nẵng cực kỳ chuẩn xác",
    content: "AI gợi ý chuẩn các quán ăn ngon ở Đà Nẵng, tính toán thời gian đi lại rất hợp lý giữa các điểm như Chùa Linh Ứng và Bán đảo Sơn Trà. Tiết kiệm cả buổi ngồi tìm kiếm.",
  },
  {
    id: "f2",
    name: "Mai Anh",
    rating: 5,
    category: "Tính năng",
    title: "Xuất Google Calendar và PDF siêu tiện lợi",
    content: "Lên lịch xong tải thẳng file ICS vào điện thoại xem từng khung giờ. Giao diện trực quan, bản đồ xem được ngay vị trí từng điểm.",
  },
  {
    id: "f3",
    name: "Quang Huy",
    rating: 5,
    category: "Phượt liên tỉnh",
    title: "Road trip Tây Bắc tính toán quãng đường rất chuẩn",
    content: "Tính năng Road trip nhiều chặng ghép được lộ trình Hà Nội - Mộc Châu - Sa Pa rõ ràng, ước lượng thời gian lái xe rất sát thực tế.",
  },
];

const faqs = [
  {
    q: "Các địa điểm du lịch trong kế hoạch có thật không?",
    a: "100% địa điểm trong kho dữ liệu đã được xác thực toạ độ GPS, giờ mở cửa và địa chỉ thực tế tại Việt Nam. AI chỉ hỗ trợ chọn lọc và tối ưu đường đi, hoàn toàn không bịa địa điểm ảo.",
  },
  {
    q: "Dự toán chi phí được tính toán như thế nào?",
    a: "Chi phí được tổng hợp từ giá vé tham quan niêm yết của các điểm di tích/khu du lịch và mức chi tiêu ẩm thực bình quân thực tế theo số lượng người tham gia chuyến đi.",
  },
  {
    q: "Tôi có thể chỉnh sửa lịch trình sau khi AI tạo xong không?",
    a: "Hoàn toàn được. Bạn có thể bấm 'Thay đổi' tại bất kỳ địa điểm nào, hoặc nhắn tin cho Trợ lý AI ở khung chat bên cạnh (ví dụ: 'Đổi quán trưa sang mì Quảng') để cập nhật ngay lập tức.",
  },
  {
    q: "Lịch trình của tôi được lưu ở đâu?",
    a: "Lịch trình được lưu an toàn gắn với phiên thiết bị của bạn. Bạn có thể đăng nhập tài khoản để đồng bộ vĩnh viễn và xem lại trên trang 'Chuyến đi của tôi'.",
  },
];

export default function Home() {
  const { t, locale } = useLocale();
  const [placesCount, setPlacesCount] = useState<number | null>(null);
  const [reviews, setReviews] = useState<Review[]>(fallbackReviews);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data.places_count === "number") setPlacesCount(data.places_count);
      })
      .catch(() => {});

    fetch(`${API_URL}/api/feedback?limit=3`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.reviews) && data.reviews.length > 0) {
          setReviews(data.reviews);
        }
      })
      .catch(() => {});

    return () => controller.abort();
  }, []);

  const goToPlanner = (value?: string) => {
    if (value) promptPlanner(value);
    else focusPlanner();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <main>
      {/* Hero Section */}
      <section className="hero" id="top">
        <div className="hero-row">
          <div className="hero-left">
            <span className="eyebrow" aria-hidden="true">
              ✨ Trợ lý Du lịch AI Thông minh · Việt Nam
            </span>
            <h1>
              Lên lịch trình thông minh,
              <br />
              khám phá trọn vẹn Việt Nam.
            </h1>
            <p className="lead">
              Chỉ cần nhập mong muốn của bạn, AI sẽ tự động phân tích toạ độ, sắp xếp tuyến đường di chuyển tối ưu và dự toán ngân sách chi tiết từng bữa ăn.
            </p>
            <div className="social-proof">
              <span className="dot" />
              <span>
                <span className="stat">100%</span> Địa điểm thực tế, tuyến đường tối ưu OSRM thật — không cần mở nhiều tab.
              </span>
            </div>
          </div>
          <Planner />
        </div>
      </section>

      {/* Curated Destinations Section */}
      <section className="landing-section" aria-labelledby="featured-heading">
        <div className="shell">
          <div className="section-head">
            <span className="eyebrow" style={{ display: "inline-block", marginBottom: "8px" }}>Điểm đến nổi bật</span>
            <h2 id="featured-heading">Khám phá các điểm đến được yêu thích nhất</h2>
            <p>Chọn nhanh hành trình mẫu được tối ưu sẵn hoặc nhấn vào để tạo lịch trình riêng cho bạn.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
            {curatedDestinations.map((dest) => (
              <div
                key={dest.name}
                className="featured-card"
                style={{
                  cursor: "pointer",
                  borderRadius: "var(--radius-xl)",
                  overflow: "hidden",
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  transition: "transform 0.2s ease, box-shadow 0.2s ease",
                }}
                onClick={() => goToPlanner(dest.prompt)}
              >
                <div
                  style={{
                    height: "180px",
                    position: "relative",
                    overflow: "hidden",
                    background: dest.fallbackGradient,
                  }}
                >
                  <img
                    src={dest.image}
                    alt={dest.name}
                    loading="lazy"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      display: "block",
                    }}
                  />
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      background: "linear-gradient(to top, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.05) 50%, transparent 100%)",
                    }}
                  />
                  <span
                    style={{
                      position: "absolute",
                      top: "12px",
                      right: "12px",
                      background: "rgba(15, 23, 42, 0.75)",
                      backdropFilter: "blur(8px)",
                      color: "#fff",
                      padding: "5px 12px",
                      borderRadius: "999px",
                      fontSize: "12px",
                      fontWeight: 800,
                      letterSpacing: "0.02em",
                      border: "1px solid rgba(255, 255, 255, 0.2)",
                    }}
                  >
                    {dest.badge}
                  </span>
                </div>
                <div style={{ padding: "20px 24px 22px", display: "flex", flexDirection: "column", gap: "8px", flex: 1 }}>
                  <h3 style={{ fontSize: "20px", margin: 0 }}>{dest.name}</h3>
                  <p style={{ color: "var(--muted)", fontSize: "14px", margin: 0 }}>{dest.tag}</p>
                  <div style={{ marginTop: "auto", paddingTop: "12px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--brand)", fontWeight: 800, fontSize: "14px" }}>
                      Tạo lịch trình ngay →
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Highlights */}
      <section className="landing-section" aria-labelledby="features-heading">
        <div className="shell">
          <div className="section-head">
            <span className="eyebrow" style={{ display: "inline-block", marginBottom: "8px" }}>Công nghệ du lịch</span>
            <h2 id="features-heading">Tính năng được thiết kế cho chuyến đi thực tế</h2>
            <p>Không chỉ là văn bản gợi ý đơn thuần, mọi kế hoạch đều được liên kết với dữ liệu toạ độ GPS và bản đồ thật.</p>
          </div>
          <div className="featured-grid feature-grid-auto">
            {highlights.map((item) => (
              <div className="card highlight-card" key={item.title} style={{ padding: "28px", borderRadius: "var(--radius-lg)" }}>
                <div className="highlight-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <span style={{ fontSize: "32px" }}>{item.icon}</span>
                  <span className="eyebrow" style={{ fontSize: "11.5px", padding: "4px 10px" }}>{item.badge}</span>
                </div>
                <h3 style={{ fontSize: "19px", margin: "0 0 8px" }}>{item.title}</h3>
                <p style={{ color: "var(--muted)", fontSize: "14.5px", lineHeight: 1.6, margin: 0 }}>{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="landing-section" aria-labelledby="how-heading">
        <div className="shell">
          <div className="section-head">
            <span className="eyebrow" style={{ display: "inline-block", marginBottom: "8px" }}>Đơn giản & Nhanh chóng</span>
            <h2 id="how-heading">3 bước để bắt đầu chuyến đi</h2>
            <p>Từ ý tưởng ban đầu đến kế hoạch chi tiết từng phút trên tay bạn.</p>
          </div>
          <div className="steps">
            {steps.map((s) => (
              <article className="step" key={s.step} style={{ padding: "28px", borderRadius: "var(--radius-lg)" }}>
                <h3 style={{ fontSize: "19px", margin: "0 0 10px" }}>{s.title}</h3>
                <p style={{ color: "var(--muted)", fontSize: "14.5px", lineHeight: 1.6, margin: 0 }}>{s.desc}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Road trip banner */}
      <section className="landing-section" aria-labelledby="tools-heading">
        <div className="shell">
          <div className="card roadtrip-banner" style={{ padding: "40px", borderRadius: "var(--radius-xl)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "24px", background: "linear-gradient(135deg, var(--surface), var(--surface-2))", border: "1px solid var(--line)" }}>
            <div style={{ maxWidth: "680px" }}>
              <span className="eyebrow" style={{ marginBottom: "10px", display: "inline-block" }}>Lộ trình xuyên Việt</span>
              <h2 id="tools-heading" style={{ fontSize: "clamp(26px, 3.5vw, 36px)", margin: "0 0 10px" }}>
                Road Trip Builder — Xếp tuyến phượt đa điểm dừng
              </h2>
              <p style={{ color: "var(--muted)", fontSize: "16px", lineHeight: 1.6, margin: 0 }}>
                Tự do thiết lập danh sách điểm dừng chân, tính toán quãng đường lái xe thực tế, thời gian di chuyển và bản đồ lộ trình chi tiết.
              </p>
            </div>
            <Link
              href="/roadtrip"
              className="primary"
              style={{
                padding: "14px 28px",
                borderRadius: "var(--radius-full)",
                fontWeight: 800,
                fontSize: "15px",
                textDecoration: "none",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                whiteSpace: "nowrap",
              }}
            >
              Tạo lộ trình phượt →
            </Link>
          </div>
        </div>
      </section>

      {/* Community Testimonials */}
      <section className="landing-section" aria-labelledby="reviews-heading">
        <div className="shell">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "36px", flexWrap: "wrap", gap: "16px" }}>
            <div className="section-head" style={{ margin: 0 }}>
              <span className="eyebrow" style={{ display: "inline-block", marginBottom: "8px" }}>Cộng đồng du lịch</span>
              <h2 id="reviews-heading">Khách du lịch nói gì về Mình Đi Đâu Thế</h2>
              <p>Đánh giá chân thực từ những người dùng đã lên kế hoạch và trải nghiệm thực tế.</p>
            </div>
            <Link
              href="/feedback"
              className="secondary"
              style={{
                padding: "10px 20px",
                borderRadius: "var(--radius-full)",
                fontWeight: 700,
                fontSize: "13.5px",
                textDecoration: "none",
                border: "1px solid var(--line-2)",
              }}
            >
              Xem tất cả đánh giá & Gửi góp ý →
            </Link>
          </div>

          <div className="featured-grid">
            {reviews.map((rev) => (
              <article
                key={rev.id}
                className="card"
                style={{
                  padding: "24px",
                  borderRadius: "var(--radius-lg)",
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: "16px", color: "var(--ink)" }}>{rev.name}</strong>
                  <span style={{ color: "#f59e0b", fontSize: "14px" }}>
                    {"★".repeat(rev.rating || 5)}
                  </span>
                </div>
                <h4 style={{ fontSize: "15.5px", margin: 0, fontWeight: 700, color: "var(--ink)" }}>{rev.title}</h4>
                <p style={{ color: "var(--muted)", fontSize: "14px", lineHeight: 1.6, margin: 0, flex: 1 }}>
                  &ldquo;{rev.content}&rdquo;
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="landing-section" aria-labelledby="faq-heading">
        <div className="shell">
          <div className="section-head">
            <span className="eyebrow" style={{ display: "inline-block", marginBottom: "8px" }}>Hỏi & Đáp</span>
            <h2 id="faq-heading">Câu hỏi thường gặp</h2>
            <p>Giải đáp thắc mắc về cách AI tính toán và sắp xếp lịch trình cho bạn.</p>
          </div>
          <div className="faq-list">
            {faqs.map((faq) => (
              <details className="faq-item" key={faq.q}>
                <summary>{faq.q}</summary>
                <div className="faq-body">{faq.a}</div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="landing-section" aria-labelledby="cta-heading">
        <div className="shell">
          <div className="cta-banner" style={{ textAlign: "center", padding: "56px 32px", borderRadius: "var(--radius-xl)" }}>
            <h2 id="cta-heading" style={{ fontSize: "clamp(28px, 4vw, 42px)", margin: "0 0 14px" }}>
              Sẵn sàng cho chuyến du lịch tiếp theo?
            </h2>
            <p style={{ maxWidth: "560px", margin: "0 auto 28px", fontSize: "17px", lineHeight: 1.6, opacity: 0.9 }}>
              Lên lịch trình thông minh hoàn toàn miễn phí chỉ trong vài giây. Khám phá trọn vẹn vẻ đẹp Việt Nam theo cách của bạn.
            </p>
            <button
              type="button"
              className="primary"
              onClick={() => goToPlanner()}
              style={{
                padding: "16px 36px",
                borderRadius: "var(--radius-full)",
                fontSize: "16px",
                fontWeight: 900,
                cursor: "pointer",
                background: "#fff",
                color: "var(--brand)",
                border: "none",
                boxShadow: "0 10px 25px rgba(0,0,0,0.15)",
              }}
            >
              Bắt đầu tạo lịch trình ngay
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
