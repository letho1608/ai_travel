"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale } from "@/components/LocaleProvider";

const links: Array<[string, string]> = [
  ["/history", "trips"],
  ["/feedback", "feedback"],
];

export default function Navigation() {
  const { t } = useLocale();
  const pathname = usePathname();
  const [hasAuth, setHasAuth] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    try {
      const auth = Boolean(localStorage.getItem("auth_token"));
      const role = localStorage.getItem("user_role");
      const adminTok = sessionStorage.getItem("admin_token");
      setHasAuth(auth);
      setIsAdmin(role === "admin" || Boolean(adminTok));
    } catch {}
  }, [pathname]);

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  function logout() {
    try {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("user_role");
      sessionStorage.removeItem("admin_token");
    } catch {}
    setHasAuth(false);
    setIsAdmin(false);
  }

  return (
    <nav className="nav" aria-label="Main">
      <Link className="brand" href="/">
        <img src="/brand/logo-mark.png" alt="" aria-hidden="true" />
        Mình Đi Đâu Thế
      </Link>
      <div className="nav-links">
        {links.map(([href, key]) => (
          <Link key={href} href={href} className={isActive(href) ? "active" : undefined}>
            {t(key as "trips")}
          </Link>
        ))}
        {isAdmin && (
          <span className="nav-admin">
            <Link href="/admin">Admin</Link>
          </span>
        )}
        {hasAuth ? (
          <Link href="/" className="nav-cta" onClick={logout}>
            <svg className="nav-account-icon" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8.5" />
              <circle cx="12" cy="9.5" r="2.5" />
              <path d="M7.8 17.1c.9-2.2 2.3-3.3 4.2-3.3s3.3 1.1 4.2 3.3" />
            </svg>
            <span>{t("logout")}</span>
          </Link>
        ) : (
          <Link href="/login" className="nav-cta">
            <svg className="nav-account-icon" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8.5" />
              <circle cx="12" cy="9.5" r="2.5" />
              <path d="M7.8 17.1c.9-2.2 2.3-3.3 4.2-3.3s3.3 1.1 4.2 3.3" />
            </svg>
            <span>{t("login")}</span>
          </Link>
        )}
      </div>
    </nav>
  );
}
