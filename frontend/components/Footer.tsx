"use client";

import Link from "next/link";
import Image from "next/image";
import { useLocale } from "@/components/LocaleProvider";

export default function Footer() {
  const { t } = useLocale();
  return (
    <footer className="site-footer">
      <div className="shell">
        <div className="footer-grid">
          <div>
            <div className="footer-brand"><img src="/brand/logo-mark.png" alt="" aria-hidden="true" />Mình Đi Đâu Thế</div>
            <p className="disclaimer">{t("footerTagline")}</p>
          </div>
          <div className="footer-col">
            <h4>{t("footerProduct")}</h4>
            <Link href="/">{t("heroEyebrow" as any) || "Lên lịch trình"}</Link>
            <Link href="/history">{t("trips")}</Link>
            <Link href="/feedback">{t("feedback")}</Link>
          </div>
          <div className="footer-col">
            <h4>{t("footerCompany")}</h4>
            <Link href="/">{t("footerAbout")}</Link>
            <Link href="/support">Hỗ trợ & Trợ giúp</Link>
          </div>
          <div className="footer-col">
            <h4>{t("footerLegal")}</h4>
            <Link href="/terms">Điều khoản</Link>
            <Link href="/privacy">Bảo mật</Link>
          </div>
        </div>
        <div className="footer-bottom">
          <span>{t("footerRights")}</span>
          <span>{t("footerMadeIn")}</span>
        </div>
      </div>
    </footer>
  );
}
