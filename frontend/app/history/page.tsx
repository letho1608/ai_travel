"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale } from "@/components/LocaleProvider";
import { API_URL } from "@/lib/api";
import { getSession } from "@/lib/session";
import type { Plan } from "@/lib/types";

type StoredPlan = { token: string; ke_hoach: Plan };
type Notification = { id: string; loai: "trip_24h"; noi_dung: string; da_doc: boolean; plan_title?: string };
type HistoryFilter = "all" | "recent" | "upcoming";

const isStoredPlan = (value: unknown): value is StoredPlan => {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  if (typeof item.token !== "string" || !item.ke_hoach || typeof item.ke_hoach !== "object") return false;
  const plan = item.ke_hoach as Record<string, unknown>;
  return typeof plan.tieu_de === "string" && typeof plan.tom_tat === "string" && typeof plan.thoi_luong === "string" && typeof plan.tong_chi_phi === "number" && Number.isFinite(plan.tong_chi_phi) && (plan.ngay_di === undefined || typeof plan.ngay_di === "string");
};
const isNotification = (value: unknown): value is Notification => {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return typeof item.id === "string" && item.loai === "trip_24h" && typeof item.noi_dung === "string" && typeof item.da_doc === "boolean" && (item.plan_title === undefined || typeof item.plan_title === "string");
};
const planDate = (plan: Plan) => {
  if (!plan.ngay_di || !/^\d{4}-\d{2}-\d{2}$/.test(plan.ngay_di)) return null;
  const parsed = new Date(`${plan.ngay_di}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  const [year, month, day] = plan.ngay_di.split("-").map(Number);
  return parsed.getFullYear() === year && parsed.getMonth() === month - 1 && parsed.getDate() === day ? parsed : null;
};
const formatDate = (plan: Plan) => {
  const date = planDate(plan);
  return date ? new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date) : "Kế hoạch đã lưu";
};
const formatCost = (cost: number) => cost > 0 ? `~ ${new Intl.NumberFormat("vi-VN").format(cost)} VNĐ` : null;

export default function History() {
  const { t } = useLocale();
  const [plans, setPlans] = useState<StoredPlan[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [notificationsLoading, setNotificationsLoading] = useState(true);
  const [planError, setPlanError] = useState(false);
  const [notificationError, setNotificationError] = useState(false);
  const [mutationError, setMutationError] = useState(false);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const pendingRef = useRef(new Set<string>());

  useEffect(() => {
    const controller = new AbortController();
    const session = getSession();
    const token = localStorage.getItem("auth_token") ?? "";
    const headers = { "X-Session-Id": session, Authorization: `Bearer ${token}` };
    fetch(`${API_URL}/api/plans`, { headers, signal: controller.signal })
      .then(async response => {
        const data = await response.json();
        if (!response.ok || !Array.isArray(data.ds_ke_hoach) || !data.ds_ke_hoach.every(isStoredPlan)) throw new Error("invalid plans response");
        setPlans(data.ds_ke_hoach);
      })
      .catch(error => { if (error.name !== "AbortError") setPlanError(true); })
      .finally(() => { if (!controller.signal.aborted) setPlansLoading(false); });
    fetch(`${API_URL}/api/notifications`, { headers, signal: controller.signal })
      .then(async response => {
        const data = await response.json();
        if (!response.ok || !Array.isArray(data.items) || !data.items.every(isNotification)) throw new Error("invalid notifications response");
        setNotifications(data.items);
      })
      .catch(error => { if (error.name !== "AbortError") setNotificationError(true); })
      .finally(() => { if (!controller.signal.aborted) setNotificationsLoading(false); });
    return () => controller.abort();
  }, []);

  async function markRead(item: Notification) {
    if (pendingRef.current.has(item.id)) return;
    pendingRef.current.add(item.id);
    setPending(values => new Set(values).add(item.id));
    setMutationError(false);
    try {
      const session = getSession();
      const token = localStorage.getItem("auth_token") || "";
      const response = await fetch(`${API_URL}/api/notifications/${item.id}`, { method: "PATCH", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body:JSON.stringify({ma_phien:session}) });
      if (!response.ok) throw new Error("mark read failed");
      setNotifications(values => values.map(value => value.id === item.id ? { ...value, da_doc: true } : value));
    } catch { setMutationError(true); }
    finally {
      pendingRef.current.delete(item.id);
      setPending(values => { const next = new Set(values); next.delete(item.id); return next; });
    }
  }

  const today = useMemo(() => { const date = new Date(); date.setHours(0, 0, 0, 0); return date; }, []);
  const visiblePlans = useMemo(() => plans.filter(({ ke_hoach }) => {
    if (filter === "all") return true;
    const date = planDate(ke_hoach);
    if (!date) return false;
    return filter === "upcoming" ? date >= today : date < today;
  }), [filter, plans, today]);
  const planMessage = plansLoading ? t("loading") : planError ? t("loadFailed") : "";
  const showEmpty = !plansLoading && !planError && plans.length === 0;
  const busy = plansLoading || notificationsLoading;

  return <main className="history-page" aria-busy={busy}>
    {notifications.length > 0 && <section className="history-notifications" aria-label={t("notifications")}>
      {notifications.map(item => <article className={`history-notification ${item.da_doc ? "read" : ""}`} key={item.id}><span>{t("tripTomorrow", { title: item.plan_title || t("trips") })}</span>{!item.da_doc && <button className="history-text-button" disabled={pending.has(item.id)} onClick={() => markRead(item)}>{t("markRead")}</button>}</article>)}
    </section>}
    <div role="status" aria-live="polite" className="history-messages">{planMessage && <p className={planError ? "error" : "lead"}>{planMessage}</p>}{notificationsLoading && !plansLoading && <p className="lead">{t("loading")}</p>}{notificationError && <p className="error">{t("notificationsFailed")}</p>}{mutationError && <p className="error">{t("markReadFailed")}</p>}</div>
    {showEmpty ? <section className="empty-state"><div className="empty-art" aria-hidden="true"/><h2>{t("noTrips")}</h2><p className="lead">Tạo kế hoạch đầu tiên để lưu lại hành trình của bạn.</p><Link className="primary" href="/">+ Tạo kế hoạch mới</Link></section> : !plansLoading && !planError && <div className="history-layout">
      <aside className="history-sidebar"><div className="history-sidebar-head"><h2>Lịch sử kế hoạch</h2><p>Các chuyến đi gần đây của bạn</p></div><nav className="history-plan-nav" aria-label="Danh sách kế hoạch">{plans.map(item => <Link key={item.token} href={`/plan/${item.token}`}><span>{item.ke_hoach.tieu_de}</span><span aria-hidden="true">›</span></Link>)}</nav><Link className="history-create" href="/"><span aria-hidden="true">＋</span>Tạo kế hoạch mới</Link></aside>
      <section className="history-content"><header className="history-header"><div><h1>Kế hoạch của bạn</h1><p>Xem lại lịch trình đã tạo hoặc tiếp tục các chuyến đi dự định.</p></div><div className="history-filters" aria-label="Lọc kế hoạch">{([{"id":"all","label":"Tất cả"},{"id":"recent","label":"Gần đây"},{"id":"upcoming","label":"Dự định"}] as const).map(item => <button type="button" key={item.id} aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label}</button>)}</div></header>
        {visiblePlans.length === 0 ? <div className="history-filter-empty">Không có kế hoạch phù hợp với bộ lọc này.</div> : <div className="history-grid">{visiblePlans.map(item => { const date = planDate(item.ke_hoach); const upcoming = Boolean(date && date >= today); const cost = formatCost(item.ke_hoach.tong_chi_phi); return <article className="history-card" key={item.token}><div className="history-card-top">{date ? <time dateTime={item.ke_hoach.ngay_di}>{formatDate(item.ke_hoach)}</time> : <span>{formatDate(item.ke_hoach)}</span>}<span className={`history-badge ${upcoming ? "upcoming" : "complete"}`}>{upcoming ? "Dự định" : "Đã lưu"}</span></div><h2>{item.ke_hoach.tieu_de}</h2><div className="history-meta"><span>{item.ke_hoach.thoi_luong}</span>{cost && <span>{cost}</span>}</div><p>{item.ke_hoach.tom_tat}</p><footer><Link href={`/plan/${item.token}`}>Xem chi tiết <span aria-hidden="true">→</span></Link></footer></article>; })}</div>}
      </section>
    </div>}
  </main>;
}
