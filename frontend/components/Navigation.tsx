"use client";

import Link from "next/link";
import { useLocale } from "@/components/LocaleProvider";

export default function Navigation(){
  const {t}=useLocale();
  return <nav className="nav">
    <Link className="brand" href="/">Minh Di Dau The</Link>
    <div>
      <Link href="/roadtrip">{t("roadtrip")}</Link>
      <Link href="/explore">{t("inventory")}</Link>
      <Link href="/history">{t("trips")}</Link>
      <Link href="/settings">{t("settings")}</Link>
      <Link href="/login">{t("login")}</Link>
      <Link href="/admin">Admin</Link>
    </div>
  </nav>;
}
