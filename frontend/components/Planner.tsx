"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { API_URL, consumePlanStream } from "@/lib/api";
import { useLocale } from "@/components/LocaleProvider";
import { getSession, setSession } from "@/lib/session";
import type { PlannerTranslationKey } from "@/lib/i18n-core";

export default function Planner() {
  const { locale, t } = useLocale();
  const ideaKeys = ["ideaCoffee", "ideaFood", "ideaCulture"] as const;
  const [context, setContext] = useState(() => t("ideaCoffee"));
  const [people, setPeople] = useState<number | "">(2);
  const [needsDuration, setNeedsDuration] = useState(false);
  const [statusKey, setStatusKey] = useState<PlannerTranslationKey | null>(null);
  const [errorKey, setErrorKey] = useState<PlannerTranslationKey | null>(null);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const mounted = useRef(true);
  const controllerRef = useRef<AbortController | null>(null);
  const previousDefault = useRef(context);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const next = t("ideaCoffee");
    setContext((current) => (current === previousDefault.current ? next : current));
    previousDefault.current = next;
  }, [locale, t]);

  const safeStatusKey = (value: string): PlannerTranslationKey =>
    value === "finding_places" ? "findingPlaces" : value === "routing_plan" ? "routingPlan" : "working";

  function requestNonce(fingerprint: string) {
    const key = "plan-generate-nonce";
    try {
      const cached = JSON.parse(sessionStorage.getItem(key) || "null") as {
        fingerprint?: string;
        nonce?: string;
      } | null;
      if (cached?.fingerprint === fingerprint && cached.nonce) return cached.nonce;
      const nonce = crypto.randomUUID();
      sessionStorage.setItem(key, JSON.stringify({ fingerprint, nonce }));
      return nonce;
    } catch {
      return crypto.randomUUID();
    }
  }

  function clearNonce() {
    try {
      sessionStorage.removeItem("plan-generate-nonce");
    } catch {}
  }

  function normalizeText(value: string) {
    return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function inferDuration(value: string) {
    const normalized = normalizeText(value);
    if (/(?:vai ngay|2 ngay|hai ngay|3 ngay|ba ngay|4 ngay|bon ngay|nhieu ngay|multi|multiple)/.test(normalized)) return "nhieu_ngay";
    if (/(?:vai gio|2 gio|3 gio|may tieng|few hours)/.test(normalized)) return "vai_gio";
    if (/(?:nua ngay|half day|buoi sang|buoi chieu|morning|afternoon)/.test(normalized)) return "nua_ngay";
    if (/(?:ca ngay|mot ngay|1 ngay|nguyen ngay|full day|one day|cuoi tuan|weekend)/.test(normalized)) return "ca_ngay";
    return null;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    const validPeople =
      typeof people === "number" &&
      Number.isFinite(people) &&
      Number.isInteger(people) &&
      people >= 1 &&
      people <= 30;
    if (!context.trim() || !validPeople) {
      setErrorKey("generateFailed");
      return;
    }
    const duration = inferDuration(context);
    if (!duration) {
      setNeedsDuration(true);
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    submitting.current = true;
    setBusy(true);
    setNeedsDuration(false);
    setErrorKey(null);
    setStatusKey("sendingRequest");
    const session = getSession();
    const fingerprint = JSON.stringify({ context: context.trim(), duration, people, locale, session });
    const nonce = requestNonce(fingerprint);
    const controller = new AbortController();
    controllerRef.current = controller;
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(`${API_URL}/api/plan/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          context,
          location: { lat: 21.0285, lng: 105.8542 },
          thoi_luong: duration,
          so_nguoi: people,
          ngan_sach: 1000000,
          ma_phien: session,
          ngon_ngu: locale,
          nonce,
        }),
      });
      if (response.status === 401) {
        try {
          localStorage.removeItem("auth_token");
          localStorage.removeItem("ma_phien");
        } catch {}
        window.location.href = "/login";
        return;
      }
      const result = await consumePlanStream(response, (value) => {
        if (mounted.current) setStatusKey(safeStatusKey(value));
      });
      if (!mounted.current) return;
      if (
        typeof result.token !== "string" ||
        !/^[A-Za-z0-9_-]+$/.test(result.token) ||
        typeof result.ma_phien !== "string" ||
        !result.ma_phien
      ) {
        throw new Error("invalid result");
      }
      clearNonce();
      setSession(result.ma_phien);
      location.assign(`/plan/${result.token}`);
    } catch (cause) {
      if (mounted.current) {
        setStatusKey(null);
        setErrorKey(cause instanceof DOMException && cause.name === "AbortError" ? "generateTimeout" : "generateFailed");
      }
    } finally {
      clearTimeout(timeout);
      if (controllerRef.current === controller) controllerRef.current = null;
      submitting.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  return (
    <form className="planner" onSubmit={submit}>
      <div className="chat-welcome">
        <span className="assistant-dot" />
        <p className="bubble assistant">{t("chatWelcome")}</p>
      </div>
      <div className="quick-actions" aria-label={t("dayPrompt")}>
        {ideaKeys.map((key) => {
          const idea = t(key);
          return (
            <button
              type="button"
              className="chip"
              key={key}
              aria-pressed={context === idea}
              onClick={() => {
                setContext(idea);
                setNeedsDuration(false);
              }}
              disabled={busy}
            >
              {idea}
            </button>
          );
        })}
      </div>
      <div className="chat-box">
        <input
          id="planner-context"
          value={context}
          maxLength={500}
          onChange={(event) => {
            setContext(event.target.value);
            setNeedsDuration(false);
          }}
          placeholder={t("chatPlaceholder")}
          aria-label={t("chatPlaceholder")}
          required
          disabled={busy}
        />
        <button type="submit" disabled={busy} aria-label={t("sendChat")}>
          ↑
        </button>
      </div>
      {needsDuration && (
        <div className="status duration-ask" role="status" aria-live="polite">
          {t("dayPrompt")} {t("durationLabel")}: {t("fewHours")}, {t("halfDay")}, {t("fullDay")} {t("multiDay")}
        </div>
      )}
      <label htmlFor="planner-people">{t("peopleLabel")}</label>
      <input
        id="planner-people"
        type="number"
        min="1"
        max="30"
        step="1"
        value={people}
        onChange={(event) => setPeople(event.target.value === "" ? "" : event.target.valueAsNumber)}
        required
        disabled={busy}
      />
      {statusKey && (
        <div className="status" role="status" aria-live="polite">
          {t(statusKey)}
        </div>
      )}
      {errorKey && (
        <div className="error retry-panel" role="alert">
          <span>{t(errorKey)}</span>
          <button type="submit" className="secondary retry-action" disabled={busy}>
            {t("retryCreate")}
          </button>
        </div>
      )}
      <p className="disclaimer">{t("dataNotice")}</p>
      <p className="disclaimer">{t("disclaimer")}</p>
    </form>
  );
}
