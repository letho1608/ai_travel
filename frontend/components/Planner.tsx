"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { API_URL, consumePlanStream } from "@/lib/api";
import { useLocale } from "@/components/LocaleProvider";
import { getSession, setSession } from "@/lib/session";
import type { PlannerTranslationKey } from "@/lib/i18n-core";

type Duration = "vai_gio" | "nua_ngay" | "ca_ngay" | "nhieu_ngay";
type ChatMessage = { id: number; role: "user" | "assistant"; text: string };

export default function Planner() {
  const { locale, t } = useLocale();
  const ideaKeys = ["ideaCoffee", "ideaFood", "ideaCulture"] as const;
  const [context, setContext] = useState(() => t("ideaCoffee"));
  const [people, setPeople] = useState<number | "">(2);
  const [needsDuration, setNeedsDuration] = useState(false);
  const [pendingContext, setPendingContext] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [statusKey, setStatusKey] = useState<PlannerTranslationKey | null>(null);
  const [errorKey, setErrorKey] = useState<PlannerTranslationKey | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const mounted = useRef(true);
  const controllerRef = useRef<AbortController | null>(null);
  const previousDefault = useRef(context);
  const messageId = useRef(0);
  const lastRequest = useRef<{ context: string; duration: Duration } | null>(null);
  const transcriptEnd = useRef<HTMLDivElement | null>(null);

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

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "nearest" });
  }, [messages]);

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

  function inferDuration(value: string): Duration | null {
    const normalized = normalizeText(value);
    if (/(?:vai ngay|2 ngay|hai ngay|3 ngay|ba ngay|4 ngay|bon ngay|nhieu ngay|multi|multiple)/.test(normalized)) return "nhieu_ngay";
    if (/(?:vai gio|2 gio|3 gio|may tieng|few hours)/.test(normalized)) return "vai_gio";
    if (/(?:nua ngay|half day|buoi sang|buoi chieu|morning|afternoon)/.test(normalized)) return "nua_ngay";
    if (/(?:ca ngay|mot ngay|1 ngay|nguyen ngay|full day|one day|cuoi tuan|weekend)/.test(normalized)) return "ca_ngay";
    return null;
  }

  function durationQuestion() {
    return `${t("dayPrompt")} ${t("durationLabel")}: ${t("fewHours")}, ${t("halfDay")}, ${t("fullDay")}, ${t("multiDay")}.`;
  }

  function addMessage(role: ChatMessage["role"], text: string) {
    setMessages((current) => [...current, { id: ++messageId.current, role, text }]);
  }

  async function generatePlan(requestContext: string, duration: Duration) {
    const validPeople =
      typeof people === "number" &&
      Number.isFinite(people) &&
      Number.isInteger(people) &&
      people >= 1 &&
      people <= 30;
    if (!requestContext.trim() || !validPeople) {
      setErrorKey("generateFailed");
      return;
    }
    lastRequest.current = { context: requestContext, duration };
    submitting.current = true;
    setBusy(true);
    setNeedsDuration(false);
    setErrorKey(null);
    setErrorDetail(null);
    setStatusKey("sendingRequest");
    const session = getSession();
    const fingerprint = JSON.stringify({ context: requestContext.trim(), duration, people, locale, session });
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
          context: requestContext,
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
        if (cause instanceof DOMException && cause.name === "AbortError") {
          setErrorKey("generateTimeout");
          setErrorDetail(null);
        } else {
          setErrorKey("generateFailed");
          const message = cause instanceof Error ? cause.message.trim() : "";
          setErrorDetail(
            message && message !== "Không thể tạo kế hoạch" && message !== "invalid result"
              ? message
              : null,
          );
        }
      }
    } finally {
      clearTimeout(timeout);
      if (controllerRef.current === controller) controllerRef.current = null;
      submitting.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  function answerDuration(answer: string, duration = inferDuration(answer)) {
    if (submitting.current || !pendingContext) return;
    addMessage("user", answer);
    setContext("");
    if (!duration) {
      addMessage("assistant", durationQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    const validPeople =
      typeof people === "number" && Number.isFinite(people) && Number.isInteger(people) && people >= 1 && people <= 30;
    if (!validPeople) {
      setErrorKey("generateFailed");
      return;
    }
    const requestContext = `${pendingContext.trim()}\n${answer.trim()}`;
    setPendingContext(null);
    setNeedsDuration(false);
    void generatePlan(requestContext, duration);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    const answer = context.trim();
    if (needsDuration) {
      if (answer) answerDuration(answer);
      return;
    }
    const validPeople =
      typeof people === "number" && Number.isFinite(people) && Number.isInteger(people) && people >= 1 && people <= 30;
    if (!answer || !validPeople) {
      setErrorKey("generateFailed");
      return;
    }
    addMessage("user", answer);
    const duration = inferDuration(answer);
    if (!duration) {
      setPendingContext(answer);
      setNeedsDuration(true);
      setContext("");
      addMessage("assistant", durationQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    void generatePlan(answer, duration);
  }

  function retryGenerate() {
    const request = lastRequest.current;
    if (!request || submitting.current) return;
    void generatePlan(request.context, request.duration);
  }

  return (
    <form className="planner" onSubmit={submit}>
      <div className="chat-welcome">
        <span className="assistant-dot" />
        <p className="bubble assistant">{t("chatWelcome")}</p>
      </div>
      {messages.length > 0 && (
        <div className="planner-transcript" role="log" aria-live="polite" aria-relevant="additions text">
          {messages.map((message) => (
            <p className={`bubble ${message.role}`} key={message.id}>
              {message.text}
            </p>
          ))}
          {needsDuration && (
            <div className="duration-suggestions" role="group" aria-label={t("durationLabel")}>
              {([
                ["fewHours", "vai_gio"],
                ["halfDay", "nua_ngay"],
                ["fullDay", "ca_ngay"],
                ["multiDay", "nhieu_ngay"],
              ] as const).map(([key, duration]) => (
                <button type="button" className="chip" key={duration} onClick={() => answerDuration(t(key), duration)} disabled={busy}>
                  {t(key)}
                </button>
              ))}
            </div>
          )}
          <div ref={transcriptEnd} aria-hidden="true" />
        </div>
      )}
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
                setPendingContext(null);
                setMessages([]);
                setErrorKey(null);
                setErrorDetail(null);
                setStatusKey(null);
                lastRequest.current = null;
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
          <span>
            {t(errorKey)}
            {errorDetail ? ` — ${errorDetail}` : ""}
          </span>
          <button type="button" className="secondary retry-action" onClick={retryGenerate} disabled={busy}>
            {t("retryCreate")}
          </button>
        </div>
      )}
      <p className="disclaimer">{t("dataNotice")}</p>
      <p className="disclaimer">{t("disclaimer")}</p>
    </form>
  );
}
