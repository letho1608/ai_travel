"use client";

import Link from "next/link";
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
            <Link href="/roadtrip">{t("roadtrip")}</Link>
            <Link href="/explore">{t("inventory")}</Link>
            <Link href="/history">{t("trips")}</Link>
            <Link href="/settings">{t("settings")}</Link>
          </div>
          <div className="footer-col">
            <h4>{t("footerCompany")}</h4>
            <Link href="/">{t("footerAbout")}</Link>
            <Link href="/support">Support</Link>
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
