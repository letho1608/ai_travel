"use client";

import Planner from "@/components/Planner";
import { useLocale } from "@/components/LocaleProvider";

const destinations: Array<[string, string, string]> = [
  ["ideaCoffee", "☕", "coffee"],
  ["ideaFood", "🍜", "food"],
  ["ideaCulture", "🏛️", "culture"],
];

const steps: Array<[string, string]> = [
  ["step1Title", "step1Text"],
  ["step2Title", "step2Text"],
  ["step3Title", "step3Text"],
];

const faqs: Array<[string, string]> = [
  ["faq1q", "faq1a"],
  ["faq2q", "faq2a"],
  ["faq3q", "faq3a"],
];

export default function Home() {
  const { t } = useLocale();
  return (
    <main>
      <section className="hero">
        <div className="hero-left">
          <span className="eyebrow">{t("heroEyebrow")}</span>
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
      </section>

      <section className="landing-section" aria-labelledby="featured-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="featured-heading">{t("featuredTitle")}</h2>
          </div>
          <div className="featured-grid">
            {destinations.map(([key, icon, id]) => (
              <a key={key} className="featured-card" href="/" aria-label={t(key as "ideaCoffee")} onClick={(e) => { e.preventDefault(); document.getElementById("planner-context")?.focus(); }}>
                <div className="thumb">{icon}</div>
                <div className="body">
                  <h3>{t(key as "ideaCoffee")}</h3>
                  <p className="go">→ {t("createPlan")}</p>
                </div>
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-section" aria-labelledby="how-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="how-heading">{t("howTitle")}</h2>
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

      <section className="landing-section" aria-labelledby="faq-heading">
        <div className="shell">
          <div className="section-head">
            <h2 id="faq-heading">{t("faqTitle")}</h2>
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

      <section className="landing-section" aria-labelledby="cta-heading">
        <div className="shell">
          <div className="cta-banner">
            <h2 id="cta-heading">{t("ctaTitle")}</h2>
            <p className="lead">{t("heroLead")}</p>
            <a className="primary" href="#top" onClick={(e) => { e.preventDefault(); document.getElementById("planner-context")?.focus(); }}>
              {t("createPlan")}
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
