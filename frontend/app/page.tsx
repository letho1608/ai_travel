"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Planner, { focusPlanner, promptPlanner } from "@/components/Planner";
import { API_URL } from "@/lib/api";
import { useLocale } from "@/components/LocaleProvider";

const destinations: Array<[string, string, string, string]> = [
  ["ideaCoffee", "☕", "Cà phê & Ngắm phố", "Khám phá các góc cà phê view đẹp, không gian mở thư giãn tại trung tâm."],
  ["ideaFood", "🍜", "Bản đồ ẩm thực", "Thưởng thức trọn vẹn đặc sản đường phố, hàng quán lâu đời ngon nức tiếng."],
  ["ideaCulture", "🏛️", "Di sản & Văn hóa", "Hành trình tham quan các bảo tàng, di tích lịch sử và danh lam thắng cảnh."],
];

const highlights = [
  {
    title: "Tối ưu hóa đa điểm dừng",
    desc: "Tính toán khoảng cách và thời gian di chuyển chuẩn xác giữa các địa điểm bằng OSRM và OpenStreetMap.",
    icon: "🗺️",
    badge: "Smart Routing",
  },
  {
    title: "Dự toán chi phí minh bạch",
    desc: "Ước tính chi phí bình quân theo đầu người rõ ràng gồm ăn uống, vé vào cổng và phí đi lại.",
    icon: "💵",
    badge: "Cost Estimates",
  },
  {
    title: "Tích hợp thời tiết thực",
    desc: "Cập nhật dự báo nhiệt độ, khả năng mưa theo thời gian thực để sắp xếp hoạt động ngoài trời hợp lý.",
    icon: "⛅",
    badge: "Live Weather",
  },
  {
    title: "Cộng tác & Xuất file linh hoạt",
    desc: "Chia sẻ lịch trình cho bạn bè, xuất PDF đẹp mắt hoặc tải file JSON để lưu trữ tiện lợi.",
    icon: "📑",
    badge: "Export & Share",
  },
];

const steps: Array<[string, string]> = [
  ["step1Title", "step1Text"],
  ["step2Title", "step2Text"],
  ["step3Title", "step3Text"],
];

const popularCities = [
  { name: "Hà Nội", tag: "Phố cổ · Cà phê · Di sản" },
  { name: "Đà Nẵng", tag: "Biển · Ẩm thực · Cầu Rồng" },
  { name: "TP. Hồ Chí Minh", tag: "Sôi động · Ẩm thực · Check-in" },
  { name: "Đà Lạt", tag: "Không khí lạnh · Săn mây · Đồi chè" },
  { name: "Hội An", tag: "Phố đèn lồng · Hoài cổ · Thuyền hoa" },
  { name: "Nha Trang", tag: "Bãi biển · Hải sản · Đảo Yến" },
];

const faqs: Array<[string, string]> = [
  ["faq1q", "faq1a"],
  ["faq2q", "faq2a"],
  ["faq3q", "faq3a"],
];

export default function Home() {
  const { t, locale } = useLocale();
  const [placesCount, setPlacesCount] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (data && typeof data.places_count === "number") setPlacesCount(data.places_count);
      })
      .catch(() => {})
      .finally(() => clearTimeout(timer));
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, []);

  const goToPlanner = (value?: string) => {
    if (value) promptPlanner(value);
    else focusPlanner();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <main>
      <section className="hero" id="top">
        <div className="hero-row">
          <div className="hero-left">
            <span className="eyebrow" aria-hidden="true">
              AI Travel Planner · Việt Nam
            </span>
            <h1>
              {t("heroTitleFirst")}
              <br />
              {t("heroTitleSecond")}
            </h1>
            <p className="lead">{t("heroLead")}</p>
            <div className="social-proof">
              <span className="dot" />
              <span>
                <span className="stat">100%</span> {t("heroTrust")}
              </span>
            </div>
          </div>
          <Planner />
        </div>
      </section>

      {/* Featured Travel Concepts */}
      <section className="landing-section" aria-labelledby="featured-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="featured-heading">{t("featuredTitle")}</h2>
            <p>Khởi đầu chuyến phiêu lưu với những ý tưởng được tuyển chọn dành riêng cho bạn.</p>
          </div>
          <div className="featured-grid">
            {destinations.map(([key, icon, label, sub]) => (
              <a
                key={key}
                className="featured-card"
                href="#top"
                aria-label={t(key as "ideaCoffee")}
                onClick={(e) => {
                  e.preventDefault();
                  goToPlanner(t(key as "ideaCoffee"));
                }}
              >
                <div className="thumb">{icon}</div>
                <div className="body">
                  <h3>{t(key as "ideaCoffee")}</h3>
                  <p>{sub}</p>
                  <p className="go">→ {t("createPlan")}</p>
                </div>
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* Feature Highlights Grid */}
      <section className="landing-section" aria-labelledby="features-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="features-heading">Tính năng được thiết kế cho trải nghiệm du lịch thực tế</h2>
            <p>Không chỉ là văn bản gợi ý, mọi kế hoạch đều được tính toán và gắn liền với dữ liệu bản đồ thật.</p>
          </div>
          <div className="featured-grid feature-grid-auto">
            {highlights.map((item) => (
              <div className="card highlight-card" key={item.title}>
                <div className="highlight-head">
                  <span className="highlight-icon">{item.icon}</span>
                  <span className="eyebrow">{item.badge}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Popular Destinations Coverage */}
      <section className="landing-section" aria-labelledby="cities-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="cities-heading">Điểm đến thịnh hành tại Việt Nam</h2>
            <p>
              Cơ sở dữ liệu liên tục cập nhật các toạ độ du lịch, nhà hàng, quán cà phê và điểm tham quan uy tín
              {placesCount !== null ? ` — hiện có ${new Intl.NumberFormat(locale).format(placesCount)} địa điểm trong kho dữ liệu` : ""}.
            </p>
          </div>
          <div className="featured-grid city-grid-auto">
            {popularCities.map((city) => (
              <button
                type="button"
                className="card city-card"
                key={city.name}
                onClick={() => goToPlanner(`Du lịch khám phá ${city.name}`)}
              >
                <h3>{city.name}</h3>
                <p>{city.tag}</p>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="landing-section" aria-labelledby="how-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="how-heading">{t("howTitle")}</h2>
            <p>3 bước đơn giản để biến ý tưởng du lịch thành lịch trình thực thi ngay lập tức.</p>
          </div>
          <div className="steps">
            {steps.map(([titleKey, textKey]) => (
              <article className="step" key={titleKey}>
                <h3>{t(titleKey as "step1Title")}</h3>
                <p>{t(textKey as "step1Text")}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Roadtrip banner */}
      <section className="landing-section" aria-labelledby="tools-heading">
        <div className="shell">
          <div className="card roadtrip-banner">
            <div className="roadtrip-copy">
              <span className="eyebrow">Khám phá liên tỉnh</span>
              <h2 id="tools-heading">Road Trip Builder đa điểm dừng</h2>
              <p>
                Tự do thiết kế hành trình xuyên Việt, tính toán chuẩn xác quãng đường, thời gian lái xe và các trạm dừng chân đẹp nhất dọc đường.
              </p>
            </div>
            <Link href="/roadtrip" className="primary roadtrip-cta">
              Tạo lộ trình Road Trip →
            </Link>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="landing-section" aria-labelledby="faq-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="faq-heading">{t("faqTitle")}</h2>
            <p>Giải đáp thắc mắc thường gặp về độ chính xác và phương thức hoạt động của hệ thống.</p>
          </div>
          <div className="faq-list">
            {faqs.map(([questionKey, answerKey]) => (
              <details className="faq-item" key={questionKey}>
                <summary>{t(questionKey as "faq1q")}</summary>
                <div className="faq-body">{t(answerKey as "faq1a")}</div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="landing-section" aria-labelledby="cta-heading">
        <div className="shell">
          <div className="cta-banner">
            <h2 id="cta-heading">{t("ctaTitle")}</h2>
            <p className="lead">{t("heroLead")}</p>
            <a
              className="primary"
              href="#top"
              onClick={(e) => {
                e.preventDefault();
                goToPlanner();
              }}
            >
              {t("createPlan")}
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
