"use client";

import Planner from "@/components/Planner";
import { useLocale } from "@/components/LocaleProvider";

export default function Home(){
  const {t}=useLocale();
  return <main className="hero"><section><div className="eyebrow">{t("heroEyebrow")}</div><h1>{t("heroTitleFirst")}<br/>{t("heroTitleSecond")}</h1><p className="lead">{t("heroLead")}</p></section><Planner/></main>;
}
