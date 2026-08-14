"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { API_URL, consumePlanStream } from "@/lib/api";
import { useLocale } from "@/components/LocaleProvider";
import { getSession, setSession } from "@/lib/session";
import type { PlannerTranslationKey } from "@/lib/i18n-core";

type Duration = "vai_gio" | "nua_ngay" | "ca_ngay" | "nhieu_ngay";
type ChatMessage = { id: number; role: "user" | "assistant"; text: string };
type Coordinate = { lat: number; lng: number };

const DEFAULT_LOCATION: Coordinate = { lat: 21.0285, lng: 105.8542 };
const DESTINATION_LOCATIONS: { pattern: RegExp; location: Coordinate }[] = [
  { pattern: /\b(ha noi|hanoi)\b/, location: { lat: 21.0285, lng: 105.8542 } },
  { pattern: /\b(ha long|halong|quang ninh)\b/, location: { lat: 20.9712, lng: 107.0448 } },
  { pattern: /\b(da nang|danang)\b/, location: { lat: 16.0544, lng: 108.2022 } },
  { pattern: /\b(hoi an)\b/, location: { lat: 15.8801, lng: 108.338 } },
  { pattern: /\b(nha trang|khanh hoa)\b/, location: { lat: 12.2388, lng: 109.1967 } },
  { pattern: /\b(phu quoc)\b/, location: { lat: 10.2899, lng: 103.984 } },
  { pattern: /\b(sa pa|sapa)\b/, location: { lat: 22.3364, lng: 103.8438 } },
  { pattern: /\b(tp hcm|ho chi minh|sai gon|saigon)\b/, location: { lat: 10.7769, lng: 106.7009 } },
  { pattern: /\b(vung tau)\b/, location: { lat: 10.4114, lng: 107.1362 } },
  { pattern: /\b(da lat|dalat|lam dong)\b/, location: { lat: 11.9404, lng: 108.4583 } },
  { pattern: /\b(hue|thua thien hue)\b/, location: { lat: 16.4637, lng: 107.5909 } },
  { pattern: /\b(can tho)\b/, location: { lat: 10.0452, lng: 105.7469 } },
  { pattern: /\b(ninh binh)\b/, location: { lat: 20.2506, lng: 105.9745 } },
];

export default function Planner() {
  const { locale, t } = useLocale();
  const ideaKeys = ["ideaCoffee", "ideaFood", "ideaCulture"] as const;
  const [context, setContext] = useState(() => t("ideaCoffee"));
  const [people, setPeople] = useState<number | "">("");
  const [needsDuration, setNeedsDuration] = useState(false);
  const [needsDestination, setNeedsDestination] = useState(false);
  const [needsPeople, setNeedsPeople] = useState(false);
  const [pendingContext, setPendingContext] = useState<string | null>(null);
  const [pendingDuration, setPendingDuration] = useState<Duration | null>(null);
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
  const lastRequest = useRef<{ context: string; duration: Duration; people: number } | null>(null);
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
    if (/^\s*([2-9]|[12][0-9]|30)\s*$/.test(normalized)) return "nhieu_ngay";
    if (/(?:vai ngay|2 ngay|hai ngay|3 ngay|ba ngay|4 ngay|bon ngay|nhieu ngay|multi|multiple)/.test(normalized)) return "nhieu_ngay";
    if (/(?:vai gio|2 gio|3 gio|may tieng|few hours)/.test(normalized)) return "vai_gio";
    if (/(?:nua ngay|half day|buoi sang|buoi chieu|morning|afternoon)/.test(normalized)) return "nua_ngay";
    if (/(?:ca ngay|mot ngay|1 ngay|nguyen ngay|full day|one day|cuoi tuan|weekend)/.test(normalized)) return "ca_ngay";
    return null;
  }

  function validPeopleValue(value: number | ""): value is number {
    return typeof value === "number" && Number.isFinite(value) && Number.isInteger(value) && value >= 1 && value <= 30;
  }

  function inferPeople(value: string): number | null {
    const normalized = normalizeText(value);
    const bareNumber = normalized.match(/^\s*([1-9]|[12][0-9]|30)\s*$/);
    if (bareNumber) return Number(bareNumber[1]);
    const digitMatch = normalized.match(/\b([1-9]|[12][0-9]|30)\s*(?:nguoi|ng|ban|khach|pax|people|person|traveler|travelers)\b/);
    if (digitMatch) return Number(digitMatch[1]);
    const wordMap: [RegExp, number][] = [
      [/\b(mot|one)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 1],
      [/\b(hai|two)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 2],
      [/\b(ba|three)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 3],
      [/\b(bon|tu|four)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 4],
      [/\b(nam|five)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 5],
    ];
    return wordMap.find(([pattern]) => pattern.test(normalized))?.[1] ?? null;
  }

  function durationQuestion() {
    return `${t("dayPrompt")} ${t("durationLabel")}: ${t("fewHours")}, ${t("halfDay")}, ${t("fullDay")}, ${t("multiDay")}.`;
  }

  function destinationQuestion() {
    return t("destinationPrompt");
  }

  function peopleQuestion() {
    return locale === "vi" ? "Bạn đi mấy người?" : `${t("peopleLabel")}?`;
  }

  function hasDestination(value: string) {
    const normalized = normalizeText(value);
    return /\b(ha noi|hanoi|ha long|halong|da nang|hoi an|nha trang|phu quoc|sa pa|sapa|tp hcm|ho chi minh|sai gon|vung tau|da lat|hue|can tho|ninh binh)\b/.test(normalized);
  }

  function destinationLocation(value: string): Coordinate {
    const normalized = normalizeText(value);
    return DESTINATION_LOCATIONS.find((item) => item.pattern.test(normalized))?.location ?? DEFAULT_LOCATION;
  }

  function addMessage(role: ChatMessage["role"], text: string) {
    setMessages((current) => [...current, { id: ++messageId.current, role, text }]);
  }

  function continueOrAskPeople(requestContext: string, duration: Duration, peopleHint: number | null = null) {
    const travelers = peopleHint ?? inferPeople(requestContext) ?? (validPeopleValue(people) ? people : null);
    if (!travelers) {
      setPendingContext(requestContext);
      setPendingDuration(duration);
      setNeedsDuration(false);
      setNeedsDestination(false);
      setNeedsPeople(true);
      setContext("");
      addMessage("assistant", peopleQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    setPeople(travelers);
    setPendingContext(null);
    setPendingDuration(null);
    setNeedsPeople(false);
    void generatePlan(requestContext, duration, travelers);
  }

  async function generatePlan(requestContext: string, duration: Duration, travelers: number) {
    if (!requestContext.trim() || !validPeopleValue(travelers)) {
      setErrorKey("generateFailed");
      return;
    }
    lastRequest.current = { context: requestContext, duration, people: travelers };
    submitting.current = true;
    setBusy(true);
    setNeedsDuration(false);
    setNeedsDestination(false);
    setErrorKey(null);
    setErrorDetail(null);
    setStatusKey("sendingRequest");
    const session = getSession();
    const fingerprint = JSON.stringify({ context: requestContext.trim(), duration, people: travelers, locale, session });
    const nonce = requestNonce(fingerprint);
    const controller = new AbortController();
    controllerRef.current = controller;
    const timeout = setTimeout(() => controller.abort(), 180000);
    try {
      const response = await fetch(`${API_URL}/api/plan/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          context: requestContext,
          location: destinationLocation(requestContext),
          thoi_luong: duration,
          so_nguoi: travelers,
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
    const requestContext = `${pendingContext.trim()}\n${answer.trim()}`;
    if (!hasDestination(requestContext)) {
      setPendingDuration(duration);
      setNeedsDuration(false);
      setNeedsDestination(true);
      setNeedsPeople(false);
      setContext("");
      addMessage("assistant", destinationQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    continueOrAskPeople(requestContext, duration);
  }

  function answerDestination(answer: string) {
    if (submitting.current || !pendingContext || !pendingDuration) return;
    const destination = answer.trim();
    if (!destination) return;
    addMessage("user", destination);
    const requestContext = `${pendingContext.trim()}\n${destination}`;
    const duration = pendingDuration;
    setContext("");
    setNeedsDestination(false);
    continueOrAskPeople(requestContext, duration, inferPeople(destination));
  }

  function answerPeople(answer: string) {
    if (submitting.current || !pendingContext || !pendingDuration) return;
    const travelers = inferPeople(answer);
    addMessage("user", answer);
    setContext("");
    if (!travelers) {
      addMessage("assistant", peopleQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    const requestContext = `${pendingContext.trim()}\n${answer.trim()}`;
    const duration = pendingDuration;
    continueOrAskPeople(requestContext, duration, travelers);
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    const answer = context.trim();
    if (needsDuration) {
      if (answer) answerDuration(answer);
      return;
    }
    if (needsDestination) {
      answerDestination(answer);
      return;
    }
    if (needsPeople) {
      if (answer) answerPeople(answer);
      return;
    }
    if (!answer) {
      setErrorKey("generateFailed");
      return;
    }
    const peopleHint = inferPeople(answer);
    if (peopleHint) setPeople(peopleHint);
    addMessage("user", answer);
    const duration = inferDuration(answer);
    if (!duration) {
      setPendingContext(answer);
      setNeedsDuration(true);
      setNeedsPeople(false);
      setContext("");
      addMessage("assistant", durationQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    if (!hasDestination(answer)) {
      setPendingContext(answer);
      setPendingDuration(duration);
      setNeedsDestination(true);
      setNeedsPeople(false);
      setContext("");
      addMessage("assistant", destinationQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    continueOrAskPeople(answer, duration, peopleHint);
  }

  function retryGenerate() {
    const request = lastRequest.current;
    if (!request || submitting.current) return;
    void generatePlan(request.context, request.duration, request.people);
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
          {needsDestination && (
            <div className="duration-suggestions" role="group" aria-label={t("destinationPrompt")}>
              {(["Hà Nội", "Hạ Long", "Đà Nẵng"] as const).map((destination) => (
                <button type="button" className="chip" key={destination} onClick={() => answerDestination(destination)} disabled={busy}>
                  {destination}
                </button>
              ))}
            </div>
          )}
          <div ref={transcriptEnd} aria-hidden="true" />
        </div>
      )}
      <div className="chat-composer">
        <div className="quick-actions chat-prompt-chips" aria-label={t("dayPrompt")}>
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
                  setNeedsDestination(false);
                  setNeedsPeople(false);
                  setPendingContext(null);
                  setPendingDuration(null);
                  setMessages([]);
                  setPeople("");
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
        <div className="chat-box chat-input-shell">
          <span className="chat-input-icon" aria-hidden="true">
            ⌕
          </span>
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
          <button type="submit" className="chat-send" disabled={busy} aria-label={t("sendChat")}>
            ↑
          </button>
        </div>
      </div>
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
