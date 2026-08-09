"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useLocale } from "@/components/LocaleProvider";

const links: Array<[string, string]> = [
  ["/roadtrip", "roadtrip"],
  ["/explore", "inventory"],
  ["/history", "trips"],
  ["/settings", "settings"],
];

export default function Navigation() {
  const { t } = useLocale();
  const pathname = usePathname();
  const [hasAuth, setHasAuth] = useState(false);

  useEffect(() => {
    try {
      setHasAuth(Boolean(localStorage.getItem("auth_token")));
    } catch {}
  }, []);

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <nav className="nav" aria-label="Main">
      <Link className="brand" href="/">
        Mình Đi Đâu Thế
      </Link>
      <div className="nav-links">
        {links.map(([href, key]) => (
          <Link key={href} href={href} className={isActive(href) ? "active" : undefined}>
            {t(key as "roadtrip")}
          </Link>
        ))}
        {hasAuth && (
          <span className="nav-admin">
            <Link href="/admin">Admin</Link>
          </span>
        )}
        <Link href="/login" className="nav-cta">
          {t("login")}
        </Link>
      </div>
    </nav>
  );
}
