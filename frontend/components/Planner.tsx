"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { API_URL, consumePlanStream } from "@/lib/api";
import { useLocale } from "@/components/LocaleProvider";
import { getSession, setSession } from "@/lib/session";
import type { PlannerTranslationKey } from "@/lib/i18n-core";

type Duration = "vai_gio" | "nua_ngay" | "ca_ngay" | "nhieu_ngay";
type ChatMessage = { id: number; role: "user" | "assistant"; text: string };
type Coordinate = { lat: number; lng: number };
type DestinationSuggestion = { label: string; lat?: number; lng?: number; reason?: string };
type IntentTimeWindow = {
  start_hour: number;
  start_minute?: number;
  end_hour: number;
  end_minute?: number;
  minutes: number;
  label?: string | null;
};
type ParsedIntent = {
  status?: "ready_to_plan" | "ask_user_missing_fields";
  question?: string | null;
  missing_fields?: string[];
  suggestions?: DestinationSuggestion[];
  parsed?: {
    duration?: Duration | null;
    people?: number | null;
    primary_intent?: string | null;
    planner_mode?: string | null;
    duration_value?: number | null;
    duration_unit?: "minute" | "hour" | "day" | "week" | null;
    duration_minutes?: number | null;
    duration_days?: number | null;
    time_window?: IntentTimeWindow | null;
    allowed_place_themes?: string[];
    avoid_place_themes?: string[];
    destination?: { name?: string; lat?: number; lng?: number } | null;
  };
};
type IntentPolicy = {
  schema_version: "intent-parse-v2";
  primary_intent?: string | null;
  planner_mode?: string | null;
  duration?: Duration | null;
  duration_value?: number | null;
  duration_unit?: "minute" | "hour" | "day" | "week" | null;
  duration_minutes?: number | null;
  duration_days?: number | null;
  time_window?: IntentTimeWindow | null;
  allowed_place_themes: string[];
  avoid_place_themes: string[];
};

const DEFAULT_LOCATION: Coordinate = { lat: 21.0285, lng: 105.8542 };
const DESTINATION_LOCATIONS: { pattern: RegExp; location: Coordinate }[] = [
  { pattern: /\b(ha noi|hanoi)\b/, location: { lat: 21.0285, lng: 105.8542 } },
  { pattern: /\b(ha long|halong|quang ninh)\b/, location: { lat: 20.9712, lng: 107.0448 } },
  { pattern: /\b(da nang|danang)\b/, location: { lat: 16.0544, lng: 108.2022 } },
  { pattern: /\b(hoi an|pho co hoi an)\b/, location: { lat: 15.8801, lng: 108.338 } },
  { pattern: /\b(nha trang|khanh hoa)\b/, location: { lat: 12.2388, lng: 109.1967 } },
  { pattern: /\b(phu quoc|dao phu quoc)\b/, location: { lat: 10.2899, lng: 103.984 } },
  { pattern: /\b(sa pa|sapa|lao cai|fansipan)\b/, location: { lat: 22.3364, lng: 103.8438 } },
  { pattern: /\b(tp hcm|ho chi minh|sai gon|saigon)\b/, location: { lat: 10.7769, lng: 106.7009 } },
  { pattern: /\b(vung tau|ba ria vung tau)\b/, location: { lat: 10.3460, lng: 107.0843 } },
  { pattern: /\b(da lat|dalat|lam dong)\b/, location: { lat: 11.9404, lng: 108.4583 } },
  { pattern: /\b(hue|thua thien hue|co do hue)\b/, location: { lat: 16.4637, lng: 107.5909 } },
  { pattern: /\b(can tho|tay do|ninh kieu)\b/, location: { lat: 10.0452, lng: 105.7469 } },
  { pattern: /\b(ninh binh|trang an|bai dinh|tam coc)\b/, location: { lat: 20.2506, lng: 105.9745 } },
  { pattern: /\b(quy nhon|binh dinh|eo gio|ky co)\b/, location: { lat: 13.7820, lng: 109.2197 } },
  { pattern: /\b(phan thiet|mui ne|binh thuan)\b/, location: { lat: 10.9273, lng: 108.1021 } },
  { pattern: /\b(quang binh|dong hoi|phong nha)\b/, location: { lat: 17.4764, lng: 106.6022 } },
  { pattern: /\b(ha giang|dong van|ma pi leng)\b/, location: { lat: 22.8233, lng: 104.9839 } },
  { pattern: /\b(hai phong|cat ba|do son)\b/, location: { lat: 20.8449, lng: 106.6881 } },
];
const DEFAULT_DESTINATION_SUGGESTIONS: DestinationSuggestion[] = [
  "Hà Nội", "Hạ Long", "Huế", "Đà Nẵng", "Hội An", "Nha Trang", "Đà Lạt", "TP.HCM",
].map((label) => ({ label }));
const THEME_DESTINATION_FALLBACKS: Record<string, string[]> = {
  healing: ["Đà Lạt", "Sa Pa", "Ninh Bình", "Phú Quốc"],
  beach: ["Nha Trang", "Phú Quốc", "Đà Nẵng", "Vũng Tàu"],
  mountain: ["Sa Pa", "Hà Giang", "Đà Lạt", "Ninh Bình"],
  food: ["Hà Nội", "TP.HCM", "Hội An", "Huế"],
  cafe: ["Đà Lạt", "Hà Nội", "Hội An", "Đà Nẵng"],
  general_travel: ["Hà Nội", "Đà Nẵng", "Hội An", "TP.HCM"],
};
const THEME_SUGGESTION_REASON: Record<string, string> = {
  healing: "nhịp chậm, thiên nhiên yên tĩnh, dễ chữa lành",
  beach: "bãi biển, hải sản và kỳ nghỉ ven biển",
  mountain: "núi, trekking và săn mây",
  food: "ẩm thực địa phương phong phú",
  cafe: "cafe view và nhịp đi chậm",
  general_travel: "điểm đến phổ biến, dễ lập lịch",
};

const plannerPromptListeners = new Set<(value: string) => void>();

export function promptPlanner(value: string) {
  plannerPromptListeners.forEach((listener) => listener(value));
}

let focusPlannerInput: (() => void) | null = null;

export function focusPlanner() {
  focusPlannerInput?.();
}

function normalizeText(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[đĐ]/g, "d").toLowerCase();
}

function isUncertainReply(value: string): boolean {
  const normalized = normalizeText(value);
  return /\b(?:ko|khg|khong|k|chang|chua)\s*(?:biet|ro|chac|quyet)\b|\b(?:bao\s*lau|sao|the\s*nao|o?\s*dau|may\s*ngay|di\s*dau|may\s*nguoi|bao\s*nhieu|cho\s*nao)\s*cung\s*(?:duoc|dc|ok|xong|the)\b|\btuy\b|\btuy\s*(?:y|ban|ai|sao|the\s*nao|duoc)\b|\ban dinh\b|\bidk\b|\bdon'?t know\b|\bnot sure\b|\bno idea\b|\brandom\b|\bngau nhien\b|\bgoi y\b|\bbat ky\b|\bbat cu\b|\bban\s*chon\b|\bchon\s*(?:giup|ho|dum|di)\b|\bsurprise(?:\s*me)?\b|\bhay\s*chon\b/.test(normalized);
}

export default function Planner() {
  const { locale, t } = useLocale();
  const [context, setContext] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    focusPlannerInput = () => inputRef.current?.focus();
    const applyPrompt = (value: string) => {
      setContext(value);
      inputRef.current?.focus();
    };
    plannerPromptListeners.add(applyPrompt);
    return () => {
      plannerPromptListeners.delete(applyPrompt);
      if (focusPlannerInput) focusPlannerInput = null;
    };
  }, []);
  const [people, setPeople] = useState<number | "">("");
  const [needsDuration, setNeedsDuration] = useState(false);
  const [needsDestination, setNeedsDestination] = useState(false);
  const [needsPeople, setNeedsPeople] = useState(false);
  const [destinationSuggestions, setDestinationSuggestions] = useState<DestinationSuggestion[]>([]);
  const [pendingContext, setPendingContext] = useState<string | null>(null);
  const [pendingDuration, setPendingDuration] = useState<Duration | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [statusKey, setStatusKey] = useState<PlannerTranslationKey | null>(null);
  const [waitNotice, setWaitNotice] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<PlannerTranslationKey | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const mounted = useRef(true);
  const controllerRef = useRef<AbortController | null>(null);
  const messageId = useRef(0);
  const lastRequest = useRef<{ context: string; duration: Duration; people: number } | null>(null);
  const pendingIntentPolicy = useRef<IntentPolicy | null>(null);
  const pendingIntentLocation = useRef<Coordinate | null>(null);
  const transcriptEnd = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "nearest" });
  }, [messages]);

  const safeStatusKey = (value: string): PlannerTranslationKey =>
    value === "finding_places"
      ? "findingPlaces"
      : value === "long_trip_wait"
        ? "creatingPlan"
        : value === "routing_plan"
          ? "routingPlan"
          : "working";

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

  function inferClockRange(value: string): { startHour: number; minutes: number; label: string } | null {
    const normalized = normalizeText(value);
    const match = normalized.match(
      /(?:(?:tu|from)\s+)?(?:luc\s+)?(\d{1,2})(?:[:h.]\d{2})?\s*(?:gio|tieng|h(?![a-z])|hours?|hrs?)?\s*(sang|chieu|am|pm)?\s*(?:-|–|—|~|den|toi|to|until)\s*(?:luc\s+)?(\d{1,2})(?:[:h.]\d{2})?\s*(?:gio|tieng|h(?![a-z])|hours?|hrs?)?\s*(sang|chieu|toi|am|pm)?/,
    );
    if (!match) return null;
    const startHour = hourWithMeridiem(Number(match[1]), match[2]);
    const endHour = hourWithMeridiem(Number(match[3]), match[4]);
    if (startHour > 23 || endHour > 23) return null;
    let minutes = endHour * 60 - startHour * 60;
    if (minutes <= 0) minutes += 24 * 60;
    if (minutes < 45 || minutes > 16 * 60) return null;
    return { startHour, minutes, label: `${startHour}h–${endHour}h` };
  }

  function hourWithMeridiem(hour: number, meridiem: string | undefined) {
    if (!meridiem) return hour;
    if ((meridiem === "pm" || meridiem === "chieu") && hour < 12) return hour + 12;
    if ((meridiem === "am" || meridiem === "sang") && hour === 12) return 0;
    return hour;
  }

  function inferHourSpan(value: string): number | null {
    const normalized = normalizeText(value);
    const labeled = normalized.match(/\b(\d{1,2}(?:[.,]\d+)?)\s*(?:gio(?:\s+dong\s+ho)?|tieng|hours?|hrs?)\b/);
    if (labeled) {
      const hours = Number(labeled[1].replace(",", "."));
      if (hours >= 0.75 && hours <= 12) return hours;
    }
    const compact = normalized.match(/\b(\d{1,2})h\b/);
    if (compact) {
      const hours = Number(compact[1]);
      if (hours >= 1 && hours <= 12) return hours;
    }
    const words: [RegExp, number][] = [
      [/\b(mot|one)\s+(gio|tieng|hour)\b/, 1],
      [/\b(hai|two)\s+(gio|tieng|hours)\b/, 2],
      [/\b(ba|three)\s+(gio|tieng|hours)\b/, 3],
      [/\b(bon|four)\s+(gio|tieng|hours)\b/, 4],
      [/\b(nam|five)\s+(gio|tieng|hours)\b/, 5],
    ];
    return words.find(([pattern]) => pattern.test(normalized))?.[1] ?? null;
  }

  function parseSlashDate(day: string, month: string, year: string | undefined, today: Date): Date | null {
    const parsedYear = year ? Number(year.length === 2 ? `20${year}` : year) : today.getFullYear();
    const date = new Date(parsedYear, Number(month) - 1, Number(day));
    if (Number.isNaN(date.getTime()) || date.getDate() !== Number(day) || date.getMonth() !== Number(month) - 1) return null;
    return date;
  }

  function inferDateRange(value: string): { start: Date; days: number; label: string } | null {
    const normalized = normalizeText(value);
    const today = new Date();
    const slash = normalized.match(
      /(?:(?:tu|from)\s+)?(?:ngay\s+)?(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\s*(?:-|–|—|den|toi|to|until)\s*(?:ngay\s+)?(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?/,
    );
    if (slash) {
      const start = parseSlashDate(slash[1], slash[2], slash[3], today);
      let end = parseSlashDate(slash[4], slash[5], slash[6], today);
      if (start && end) {
        if (end.getTime() < start.getTime()) end = new Date(end.getFullYear() + 1, end.getMonth(), end.getDate());
        const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
        if (days >= 1 && days <= 30) {
          return { start, days, label: `${start.getDate()}/${start.getMonth() + 1}–${end.getDate()}/${end.getMonth() + 1}` };
        }
      }
    }
    const monthDays = normalized.match(/(?:tu|from)\s+ngay\s+(\d{1,2})\s+(?:den|toi|to)\s+ngay\s+(\d{1,2})/);
    if (monthDays) {
      const startDay = Number(monthDays[1]);
      const endDay = Number(monthDays[2]);
      const start = new Date(today.getFullYear(), today.getMonth(), startDay);
      let end = new Date(today.getFullYear(), today.getMonth(), endDay);
      if (end.getTime() < start.getTime()) end = new Date(today.getFullYear(), today.getMonth() + 1, endDay);
      const days = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
      if (days >= 1 && days <= 5) return { start, days, label: `${days} ngày` };
    }
    return null;
  }

  function durationFromMinutes(minutes: number): Duration {
    if (minutes <= 240) return "vai_gio";
    if (minutes <= 420) return "nua_ngay";
    return "ca_ngay";
  }

  const DAY_COUNT_WORDS: [RegExp, number][] = [
    [/\b(mot|one)\s+(ngay|day)\b/, 1],
    [/\b(hai|two)\s+(ngay|days)\b/, 2],
    [/\b(ba|three)\s+(ngay|days)\b/, 3],
    [/\b(bon|four)\s+(ngay|days)\b/, 4],
    [/\b(nam|five)\s+(ngay|days)\b/, 5],
    [/\b(sau|six)\s+(ngay|days)\b/, 6],
    [/\b(bay|seven)\s+(ngay|days)\b/, 7],
    [/\b(tam|eight)\s+(ngay|days)\b/, 8],
    [/\b(chin|nine)\s+(ngay|days)\b/, 9],
    [/\b(muoi|ten)\s+(ngay|days)\b/, 10],
  ];

  const WEEK_COUNT_WORDS: [RegExp, number][] = [
    [/\b(mot|one)\s+(tuan|week)\b/, 1],
    [/\b(hai|two)\s+(tuan|weeks)\b/, 2],
    [/\b(ba|three)\s+(tuan|weeks)\b/, 3],
    [/\b(bon|four)\s+(tuan|weeks)\b/, 4],
  ];

  function inferDayCount(value: string): number | null {
    const normalized = normalizeText(value);
    const weeks = normalized.match(/\b(\d{1,2})\s*(?:tuan|weeks?)\b/);
    if (weeks) return Math.min(Number(weeks[1]) * 7, 365);
    const wordWeeks = WEEK_COUNT_WORDS.find(([pattern]) => pattern.test(normalized));
    if (wordWeeks) return Math.min(wordWeeks[1] * 7, 365);
    const labeled = normalized.match(/\b([1-9]\d{0,2})\s*(?:ngay|days?)\b/);
    if (labeled) return Math.min(Number(labeled[1]), 365);
    const wordDays = DAY_COUNT_WORDS.find(([pattern]) => pattern.test(normalized));
    if (wordDays) return wordDays[1];
    const dates = inferDateRange(value);
    if (dates) return dates.days;
    const pair = normalized.match(/^\s*([1-9]|[12][0-9]|30)\s*[,/ ]+\s*(?:[1-9]|[12][0-9]|30)\s*$/);
    if (pair) return Number(pair[1]);
    const bareNumber = normalized.match(/^\s*([1-9]|[12][0-9]|30)\s*$/);
    if (bareNumber) return Number(bareNumber[1]);
    return null;
  }

  function inferDuration(value: string): Duration | null {
    const normalized = normalizeText(value);
    const dates = inferDateRange(value);
    if (dates && dates.days >= 2) return "nhieu_ngay";
    const clock = inferClockRange(value);
    if (clock) return durationFromMinutes(clock.minutes);
    const hours = inferHourSpan(value);
    if (hours != null) return durationFromMinutes(hours * 60);
    if (dates?.days === 1) return "ca_ngay";
    const days = inferDayCount(value);
    if (days != null) return days >= 2 ? "nhieu_ngay" : "ca_ngay";
    if (/^\s*1\s*$/.test(normalized)) return "ca_ngay";
    if (/(?:vai gio|may tieng|few hours)/.test(normalized)) return "vai_gio";
    if (/(?:nhieu ngay|multi|multiple)/.test(normalized)) return "nhieu_ngay";
    if (/(?:vai ngay|2 ngay|hai ngay|3 ngay|ba ngay|4 ngay|bon ngay)/.test(normalized)) return "nhieu_ngay";
    if (/(?:nua ngay|half day|buoi sang|buoi chieu|morning|afternoon)/.test(normalized)) return "nua_ngay";
    if (/(?:ca ngay|mot ngay|1 ngay|nguyen ngay|full day|one day|cuoi tuan|weekend)/.test(normalized)) return "ca_ngay";
    return null;
  }

  function validPeopleValue(value: number | ""): value is number {
    return typeof value === "number" && Number.isFinite(value) && Number.isInteger(value) && value >= 1 && value <= 30;
  }

  function inferPairedPeople(value: string): number | null {
    const normalized = normalizeText(value);
    const pair = normalized.match(/^\s*(?:[1-9]|[12][0-9]|30)\s*[,/]+\s*([1-9]|[12][0-9]|30)\s*$/)
      || normalized.match(/^\s*(?:[1-9]|[12][0-9]|30)\s+([1-9]|[12][0-9]|30)\s*$/);
    return pair ? Number(pair[1]) : null;
  }

  const PEOPLE_UNITS = "(?:nguoi|nguoi lon|ng|ban|dua|tre em|tre con|con|vo chong|em be|khach|pax|adults?|kids?|children|people|person|travelers?)";

  function inferPeople(value: string): number | null {
    const paired = inferPairedPeople(value);
    if (paired) return paired;
    const normalized = normalizeText(value);
    const bareNumber = normalized.match(/^\s*([1-9]|[12][0-9]|30)\s*$/);
    if (bareNumber) return Number(bareNumber[1]);
    const labeled: RegExpExecArray[] = [];
    const peoplePattern = new RegExp(`\\b([1-9]|[12][0-9]|30)\\s*${PEOPLE_UNITS}\\b`, "g");
    let peopleMatch: RegExpExecArray | null;
    while ((peopleMatch = peoplePattern.exec(normalized)) !== null) labeled.push(peopleMatch);
    if (labeled.length >= 2) {
      return Math.min(labeled.reduce((sum, match) => sum + Number(match[1]), 0), 30);
    }
    if (labeled[0]) return Math.min(Number(labeled[0][1]), 30);
    const wordMap: [RegExp, number][] = [
      [/\b(mot|one)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 1],
      [/\b(hai|two)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 2],
      [/\b(ba|three)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 3],
      [/\b(bon|tu|four)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 4],
      [/\b(nam|five)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 5],
      [/\b(sau|six)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 6],
      [/\b(bay|seven)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 7],
      [/\b(tam|eight)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 8],
      [/\b(chin|nine)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 9],
      [/\b(muoi|ten)\s+(?:nguoi|ban|khach|pax|people|person|traveler|travelers)\b/, 10],
    ];
    const wordMatch = wordMap.find(([pattern]) => pattern.test(normalized));
    if (wordMatch) return wordMatch[1];
    return /\bvo chong\b|\bcouple\b/.test(normalized) ? 2 : null;
  }

  function durationQuestion() {
    return locale === "vi"
      ? `${t("dayPrompt")} Có thể ghi 2 giờ, từ 9h đến 17h, từ 20/8 đến 22/8, hoặc chọn: ${t("fewHours")}, ${t("halfDay")}, ${t("fullDay")}, ${t("multiDay")}.`
      : `${t("dayPrompt")} You can type 2 hours, 9am to 5pm, 20/8 to 22/8, or choose: ${t("fewHours")}, ${t("halfDay")}, ${t("fullDay")}, ${t("multiDay")}.`;
  }

  function destinationQuestion() {
    const pool = destinationSuggestions.length ? destinationSuggestions : DEFAULT_DESTINATION_SUGGESTIONS;
    const labels = pool.slice(0, 4).map((item) => item.label).join(", ");
    if (locale === "vi") {
      return labels
        ? `Bạn muốn đi ở đâu? Mình gợi ý ${labels}. Chọn một điểm, hoặc bấm “Gợi ý cho tôi” để mình thiết kế hộ.`
        : t("destinationPrompt");
    }
    return labels
      ? `Where would you like to go? Suggestions: ${labels}. Pick one, or tap “Surprise me”.`
      : t("destinationPrompt");
  }

  function peopleQuestion() {
    return locale === "vi" ? "Bạn đi mấy người?" : `${t("peopleLabel")}?`;
  }

  function hasDestination(value: string) {
    const normalized = normalizeText(value);
    return DESTINATION_LOCATIONS.some((item) => item.pattern.test(normalized));
  }

  function destinationLocation(value: string): Coordinate {
    const normalized = normalizeText(value);
    return DESTINATION_LOCATIONS.find((item) => item.pattern.test(normalized))?.location ?? DEFAULT_LOCATION;
  }

  function describeTripPurpose(): string {
    const intent = pendingIntentPolicy.current?.primary_intent || "";
    const vi: Record<string, string> = {
      healing: "chữa lành",
      beach: "đi biển",
      mountain: "leo núi",
      food: "ẩm thực",
      cafe: "cà phê",
    };
    const en: Record<string, string> = {
      healing: "a healing trip",
      beach: "a beach trip",
      mountain: "a mountain trip",
      food: "a food trip",
      cafe: "a cafe trip",
    };
    return locale === "vi" ? (vi[intent] || "du lịch") : (en[intent] || "this trip");
  }

  function withSuggestionCoords(item: DestinationSuggestion): DestinationSuggestion {
    if (typeof item.lat === "number" && typeof item.lng === "number") return item;
    const location = DESTINATION_LOCATIONS.find((entry) => entry.pattern.test(normalizeText(item.label)))?.location;
    return location ? { ...item, lat: location.lat, lng: location.lng } : item;
  }

  function pickSuggestedDestination(): DestinationSuggestion {
    const intent = pendingIntentPolicy.current?.primary_intent || "general_travel";
    const reason = THEME_SUGGESTION_REASON[intent] || THEME_SUGGESTION_REASON.general_travel;
    const fallbackLabels = THEME_DESTINATION_FALLBACKS[intent] || THEME_DESTINATION_FALLBACKS.general_travel;
    const pool = (destinationSuggestions.length
      ? destinationSuggestions
      : fallbackLabels.map((label) => ({ label, reason }))
    ).map(withSuggestionCoords);
    const picked = pool[0] || withSuggestionCoords({ label: fallbackLabels[0] || "Hà Nội", reason });
    return picked.reason ? picked : { ...picked, reason };
  }

  function applyPickedDestination(picked: DestinationSuggestion, contextOverride?: string | null, durationOverride?: Duration | null) {
    const base = (contextOverride ?? pendingContext)?.trim();
    if (!base) return;
    if (typeof picked.lat === "number" && typeof picked.lng === "number") {
      pendingIntentLocation.current = { lat: picked.lat, lng: picked.lng };
    } else {
      pendingIntentLocation.current = destinationLocation(picked.label);
    }
    const purpose = describeTripPurpose();
    const reason = picked.reason ? ` ${picked.reason.charAt(0).toUpperCase()}${picked.reason.slice(1)}.` : "";
    addMessage(
      "assistant",
      locale === "vi"
        ? `Không sao — mình gợi ý ${picked.label} cho chuyến ${purpose}.${reason} Bạn vẫn có thể đổi điểm khác.`
        : `No worries — I'll go with ${picked.label} for ${purpose}.${reason} You can still change it later.`,
    );
    const requestContext = `${base}\n${picked.label}`;
    setPendingContext(requestContext);
    setContext("");
    setNeedsDestination(false);
    setDestinationSuggestions([]);
    const duration = durationOverride !== undefined ? durationOverride : pendingDuration;
    if (!duration) {
      setNeedsDuration(true);
      addMessage("assistant", durationQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    continueOrAskPeople(requestContext, duration, inferPeople(picked.label));
  }

  function addMessage(role: ChatMessage["role"], text: string) {
    setMessages((current) => [...current, { id: ++messageId.current, role, text }]);
  }

  async function parseIntent(value: string): Promise<ParsedIntent | null> {
    const response = await fetch(`${API_URL}/api/intent/parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: value, ngon_ngu: locale }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    return data && typeof data === "object" ? data as ParsedIntent : null;
  }

  function clockRangeToWindow(value: string): IntentTimeWindow | null {
    const clock = inferClockRange(value);
    if (!clock) return null;
    const endHour = (clock.startHour + Math.floor(clock.minutes / 60)) % 24;
    return {
      start_hour: clock.startHour,
      start_minute: 0,
      end_hour: endHour,
      end_minute: clock.minutes % 60,
      minutes: clock.minutes,
      label: clock.label,
    };
  }

  function policyFromIntent(intent: ParsedIntent | null, raw = ""): IntentPolicy | null {
    const parsed = intent?.parsed;
    const allowed = Array.isArray(parsed?.allowed_place_themes) ? parsed.allowed_place_themes.filter(Boolean) : [];
    const avoided = Array.isArray(parsed?.avoid_place_themes) ? parsed.avoid_place_themes.filter(Boolean) : [];
    const duration = parsed?.duration ?? inferDuration(raw);
    const durationDays = parsed?.duration_days ?? inferDayCount(raw);
    const durationMinutes = parsed?.duration_minutes ?? (inferHourSpan(raw) != null ? Math.round((inferHourSpan(raw) as number) * 60) : null);
    const timeWindow = parsed?.time_window ?? clockRangeToWindow(raw);
    if (!parsed?.primary_intent && !parsed?.planner_mode && allowed.length === 0 && avoided.length === 0 && !duration && !durationDays && !timeWindow) return null;
    return {
      schema_version: "intent-parse-v2",
      primary_intent: parsed?.primary_intent ?? null,
      planner_mode: parsed?.planner_mode ?? null,
      duration: duration ?? null,
      duration_value: parsed?.duration_value ?? durationDays ?? (durationMinutes != null ? durationMinutes / 60 : null),
      duration_unit: parsed?.duration_unit ?? (durationDays ? "day" : durationMinutes != null ? "minute" : null),
      duration_minutes: timeWindow?.minutes ?? durationMinutes ?? null,
      duration_days: durationDays && durationDays >= 2 ? durationDays : parsed?.duration_days ?? null,
      time_window: timeWindow,
      allowed_place_themes: allowed,
      avoid_place_themes: avoided,
    };
  }

  function locationFromIntent(intent: ParsedIntent | null): Coordinate | null {
    const destination = intent?.parsed?.destination;
    if (!destination || typeof destination.lat !== "number" || typeof destination.lng !== "number") return null;
    return { lat: destination.lat, lng: destination.lng };
  }

  function stripBareCounts(value: string) {
    return value
      .split("\n")
      .map((part) => part.trim())
      .filter((part) => part && !/^(?:[1-9]|[12][0-9]|30)(?:\s*[,/ ]+\s*(?:[1-9]|[12][0-9]|30))?$/.test(part))
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function inferBudget(value: string): number | null {
    const normalized = normalizeText(value);
    const million = normalized.match(/\b(\d{1,3}(?:[.,]\d+)?)\s*(?:trieu|trien|tr)\b/);
    if (million) {
      const parsed = Math.round(Number(million[1].replace(",", ".")) * 1_000_000);
      if (parsed >= 50_000 && parsed <= 100_000_000) return parsed;
    }
    const thousand = normalized.match(/\b(\d{1,6}(?:[.,]\d+)?)\s*(?:nghin|ngan|nghìn|k)\b/);
    if (thousand) {
      const parsed = Math.round(Number(thousand[1].replace(",", ".")) * 1_000);
      if (parsed >= 50_000 && parsed <= 100_000_000) return parsed;
    }
    const dong = normalized.match(/\b(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{3})?)\s*(?:d|dong|đ|vnd)\b/);
    if (dong) {
      const parsed = Number(dong[1].replace(/[.,]/g, ""));
      if (parsed >= 50_000 && parsed <= 100_000_000) return parsed;
    }
    const compact = normalized.match(/\b(\d{5,9})\s*(?:d|dong|đ|vnd)\b/);
    if (compact) {
      const parsed = Number(compact[1]);
      if (parsed >= 50_000 && parsed <= 100_000_000) return parsed;
    }
    return null;
  }

  function composeRequestContext(raw: string, duration: Duration, travelers: number) {
    const idea = stripBareCounts(raw);
    const days = inferDayCount(raw) ?? (duration === "nhieu_ngay" ? 2 : 1);
    const dayText = locale === "vi"
      ? duration === "vai_gio"
        ? "vài giờ"
        : duration === "nua_ngay"
          ? "nửa ngày"
          : duration === "ca_ngay"
            ? "1 ngày"
            : `${days} ngày`
      : duration === "vai_gio"
        ? "a few hours"
        : duration === "nua_ngay"
          ? "half day"
          : duration === "ca_ngay"
            ? "1 day"
            : `${days} days`;
    const peopleText = locale === "vi"
      ? `${travelers} người`
      : `${travelers} ${travelers === 1 ? "person" : "people"}`;
    const alreadyDays = /(?:vai gio|nua ngay|\d+\s*(?:ngay|days?|gio|tieng|hours?)|few hours|half day|\d{1,2}\s*h|\d{1,2}\s*(?:-|den|toi)\s*\d{1,2}|\d{1,2}[/\-.]\d{1,2})/.test(normalizeText(idea));
    const alreadyPeople = /\d+\s*(?:nguoi|people|person|persons|travelers?)/.test(normalizeText(idea));
    const extras = [...(alreadyDays ? [] : [dayText]), ...(alreadyPeople ? [] : [peopleText])];
    return extras.length ? `${idea}, ${extras.join(" ")}` : idea;
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
    const composedContext = composeRequestContext(requestContext, duration, travelers);
    const days = inferDayCount(composedContext) ?? inferDayCount(requestContext);
    const window = clockRangeToWindow(composedContext) ?? clockRangeToWindow(requestContext);
    pendingIntentPolicy.current = {
      schema_version: "intent-parse-v2",
      primary_intent: pendingIntentPolicy.current?.primary_intent ?? null,
      planner_mode: pendingIntentPolicy.current?.planner_mode ?? (
        days && days >= 8 ? "long_trip" : days && days >= 2 ? "multi_day_trip" : null
      ),
      duration,
      duration_value: days && days >= 2 ? days : window ? window.minutes / 60 : null,
      duration_unit: days && days >= 2 ? "day" : window ? "minute" : null,
      duration_minutes: window?.minutes ?? null,
      duration_days: days && days >= 2 ? days : null,
      time_window: window ?? null,
      allowed_place_themes: pendingIntentPolicy.current?.allowed_place_themes ?? [],
      avoid_place_themes: pendingIntentPolicy.current?.avoid_place_themes ?? [],
    };
    const nganSach = inferBudget(composedContext) ?? inferBudget(requestContext) ?? 1000000;
    const tripStart = inferDateRange(composedContext)?.start ?? inferDateRange(requestContext)?.start;
    const ngayDi = tripStart
      ? `${tripStart.getFullYear()}-${String(tripStart.getMonth() + 1).padStart(2, "0")}-${String(tripStart.getDate()).padStart(2, "0")}`
      : undefined;
    lastRequest.current = { context: composedContext, duration, people: travelers };
    submitting.current = true;
    setBusy(true);
    setNeedsDuration(false);
    setNeedsDestination(false);
    setErrorKey(null);
    setErrorDetail(null);
    setStatusKey("sendingRequest");
    const longTripWait =
      locale === "vi"
        ? "Vì bạn yêu cầu lên kế hoạch nhiều ngày nên hệ thống sẽ mất vài phút để tạo lịch trình. Bạn vui lòng đợi."
        : "Because you asked for a multi-day itinerary, the system may take a few minutes to create the plan. Please wait.";
    const overflowNotice = (days ?? 0) > 30
      ? (locale === "vi"
          ? `Úi, kế hoạch ${days} ngày hơi "khủng" so với hệ thống (tối đa 30 ngày mỗi chặng). Mình sẽ lập 30 ngày đầu, việc này có thể mất vài phút. Bạn vui lòng đợi.`
          : `A ${days}-day plan is a bit huge for the system (max 30 days per leg). I'll plan the first 30 days — this may take a few minutes. Please wait.`)
      : null;
    if (overflowNotice) addMessage("assistant", overflowNotice);
    if ((days ?? 0) >= 8) {
      setWaitNotice(longTripWait);
    } else {
      setWaitNotice(null);
    }
    const session = getSession();
    const fingerprint = JSON.stringify({ context: composedContext.trim(), duration, people: travelers, locale, session });
    const nonce = requestNonce(fingerprint);
    const controller = new AbortController();
    controllerRef.current = controller;
    const timeout = setTimeout(() => controller.abort(), 300000);
    try {
      const response = await fetch(`${API_URL}/api/plan/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          context: composedContext,
          location: pendingIntentLocation.current ?? destinationLocation(composedContext),
          thoi_luong: duration,
          so_nguoi: travelers,
          ngan_sach: nganSach,
          ...(ngayDi ? { ngay_di: ngayDi } : {}),
          ma_phien: session,
          ngon_ngu: locale,
          nonce,
          ...(pendingIntentPolicy.current ? { intent_policy: pendingIntentPolicy.current } : {}),
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
        if (!mounted.current) return;
        if (value === "long_trip_wait") setWaitNotice(longTripWait);
        setStatusKey(safeStatusKey(value));
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
        setWaitNotice(null);
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

  function durationContextLine(answer: string) {
    const trimmed = answer.trim();
    const days = inferDayCount(trimmed);
    if (days != null && /^\s*([1-9]|[12][0-9]|30)\s*$/.test(normalizeText(trimmed))) {
      return locale === "vi" ? `${days} ngày` : `${days} ${days === 1 ? "day" : "days"}`;
    }
    return trimmed;
  }

  function answerDuration(answer: string, duration = inferDuration(answer)) {
    if (submitting.current || !pendingContext) return;
    addMessage("user", answer);
    setContext("");
    if (!duration) {
      if (isUncertainReply(answer)) {
        const fallback: Duration = "ca_ngay";
        addMessage("assistant", locale === "vi"
          ? "Mình sẽ mặc định lên lịch trình trọn vẹn 1 ngày (cả ngày) nhé. Bạn có thể thay đổi sau."
          : "I'll default to a 1-day full trip. You can adjust it later.");
        duration = fallback;
      } else {
        addMessage("assistant", durationQuestion());
        setErrorKey(null);
        setStatusKey(null);
        return;
      }
    }
    const requestContext = `${pendingContext.trim()}\n${durationContextLine(answer)}`;
    const knownDestination = hasDestination(pendingContext) || pendingIntentLocation.current != null;
    if (!knownDestination && !hasDestination(requestContext)) {
      setPendingContext(requestContext);
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
    continueOrAskPeople(requestContext, duration, inferPairedPeople(answer));
  }

  function answerDestination(answer: string) {
    if (submitting.current || !pendingContext) return;
    const destination = answer.trim();
    if (!destination) return;
    addMessage("user", destination);
    if (!hasDestination(destination) && (
      isUncertainReply(destination)
      || /dau cung (?:duoc|dc)|sao cung (?:duoc|dc)|o dau cung (?:duoc|dc)|tuy|ngau nhien|random/.test(normalizeText(destination))
    )) {
      applyPickedDestination(pickSuggestedDestination());
      return;
    }
    if (!hasDestination(destination)) {
      addMessage(
        "assistant",
        locale === "vi"
          ? `Mình sẽ tìm kiếm các địa điểm tuyệt vời theo "${destination}" cho bạn nhé!`
          : `I'll find the best places for "${destination}"!`,
      );
    }
    const requestContext = `${pendingContext.trim()}\n${destination}`;
    const duration = pendingDuration;
    setContext("");
    setNeedsDestination(false);
    setDestinationSuggestions([]);
    if (!duration) {
      setPendingContext(requestContext);
      setNeedsDuration(true);
      addMessage("assistant", durationQuestion());
      setErrorKey(null);
      setStatusKey(null);
      return;
    }
    continueOrAskPeople(requestContext, duration, inferPeople(destination));
  }

  function answerPeople(answer: string) {
    if (submitting.current || !pendingContext || !pendingDuration) return;
    addMessage("user", answer);
    setContext("");
    let travelers = inferPeople(answer);
    if (travelers === null && isUncertainReply(answer)) {
      travelers = 2;
      addMessage("assistant", locale === "vi"
        ? "Mình sẽ xếp mặc định cho 2 người nhé. Bạn có thể đổi sau."
        : "I'll default to 2 people. You can adjust it later.");
    }
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

  async function submit(e: FormEvent) {
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

    try {
      const intent = await parseIntent(answer);
      pendingIntentPolicy.current = policyFromIntent(intent, answer);
      pendingIntentLocation.current = locationFromIntent(intent) ?? (hasDestination(answer) ? destinationLocation(answer) : null);
      const missing = intent?.missing_fields ?? [];
      const parsedDuration = intent?.parsed?.duration ?? inferDuration(answer);
      const parsedPeople = intent?.parsed?.people ?? peopleHint;
      const knownDestination = Boolean(intent?.parsed?.destination) || hasDestination(answer);
      if (intent?.status === "ask_user_missing_fields" && missing.includes("destination") && !knownDestination) {
        const suggestions = (intent.suggestions ?? [])
          .filter((item) => Boolean(item.label))
          .map((item) => ({ label: item.label || "", lat: item.lat, lng: item.lng, reason: item.reason }));
        setPendingContext(answer);
        setPendingDuration(parsedDuration ?? null);
        setNeedsDuration(false);
        setNeedsPeople(false);
        setContext("");
        setDestinationSuggestions(suggestions);
        if (isUncertainReply(answer)) {
          const intentKey = intent.parsed?.primary_intent || "general_travel";
          const fallbackLabel = (THEME_DESTINATION_FALLBACKS[intentKey] || THEME_DESTINATION_FALLBACKS.general_travel)[0];
          const picked = withSuggestionCoords(suggestions[0] || {
            label: fallbackLabel,
            reason: THEME_SUGGESTION_REASON[intentKey] || THEME_SUGGESTION_REASON.general_travel,
          });
          applyPickedDestination(picked, answer, parsedDuration ?? null);
          return;
        }
        setNeedsDestination(true);
        addMessage("assistant", intent.question || destinationQuestion());
        setErrorKey(null);
        setStatusKey(null);
        return;
      }
      if (intent?.status === "ask_user_missing_fields" && missing.includes("duration") && !parsedDuration) {
        setPendingContext(answer);
        setPendingDuration(null);
        setNeedsDuration(true);
        setNeedsDestination(false);
        setNeedsPeople(false);
        setContext("");
        addMessage("assistant", intent.question || durationQuestion());
        setErrorKey(null);
        setStatusKey(null);
        return;
      }
      if (intent?.status === "ask_user_missing_fields" && missing.includes("people") && parsedDuration) {
        setPendingContext(answer);
        setPendingDuration(parsedDuration);
        setNeedsPeople(true);
        setNeedsDuration(false);
        setNeedsDestination(false);
        setContext("");
        addMessage("assistant", intent.question || peopleQuestion());
        setErrorKey(null);
        setStatusKey(null);
        return;
      }
      if ((intent?.status === "ready_to_plan" || (knownDestination && parsedDuration)) && parsedDuration && parsedPeople) {
        continueOrAskPeople(answer, parsedDuration, parsedPeople);
        return;
      }
      if (knownDestination && parsedDuration && !parsedPeople) {
        setPendingContext(answer);
        setPendingDuration(parsedDuration);
        setNeedsPeople(true);
        setNeedsDuration(false);
        setNeedsDestination(false);
        setContext("");
        addMessage("assistant", intent?.question || peopleQuestion());
        setErrorKey(null);
        setStatusKey(null);
        return;
      }
      if (knownDestination && !parsedDuration) {
        setPendingContext(answer);
        setPendingDuration(null);
        setNeedsDuration(true);
        setNeedsDestination(false);
        setNeedsPeople(false);
        setContext("");
        addMessage("assistant", intent?.question || durationQuestion());
        setErrorKey(null);
        setStatusKey(null);
        return;
      }
    } catch {
      pendingIntentPolicy.current = null;
      pendingIntentLocation.current = null;
      // Fall through to the legacy local parser if the backend intent endpoint is unavailable.
    }

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
              <button
                type="button"
                className="chip"
                key="__surprise__"
                onClick={() => {
                  if (submitting.current || !pendingContext) return;
                  addMessage("user", locale === "vi" ? "Gợi ý cho tôi" : "Surprise me");
                  applyPickedDestination(pickSuggestedDestination());
                }}
                disabled={busy}
              >
                {locale === "vi" ? "✨ Gợi ý cho tôi" : "✨ Surprise me"}
              </button>
              {(destinationSuggestions.length ? destinationSuggestions : DEFAULT_DESTINATION_SUGGESTIONS).map((destination) => (
                <button
                  type="button"
                  className="chip"
                  key={destination.label}
                  onClick={() => {
                    if (typeof destination.lat === "number" && typeof destination.lng === "number") {
                      pendingIntentLocation.current = { lat: destination.lat, lng: destination.lng };
                    }
                    answerDestination(destination.label);
                  }}
                  disabled={busy}
                >
                  {destination.label}
                </button>
              ))}
            </div>
          )}
          <div ref={transcriptEnd} aria-hidden="true" />
        </div>
      )}
      <div className="chat-composer">
        {messages.length === 0 && (
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", margin: "4px 0 10px" }} aria-label="Gợi ý nhanh">
            {[
              { label: "🌿 Đà Nẵng 3N2Đ", prompt: "Lịch trình du lịch Đà Nẵng 3 ngày 2 đêm cho 2 người thích biển và hải sản" },
              { label: "🍜 Food tour Hà Nội", prompt: "Lịch trình food tour phố cổ Hà Nội 1 ngày cho 2 người thích ăn vặt" },
              { label: "🏖️ Phú Quốc 4 ngày", prompt: "Lịch trình nghỉ dưỡng Phú Quốc 4 ngày 3 đêm cho gia đình" },
              { label: "⛰️ Phượt Tây Bắc", prompt: "Lịch trình phượt Hà Giang Sa Pa 3 ngày bằng xe máy" },
              { label: "☕ Cà phê chill Đà Lạt", prompt: "Lịch trình săn mây và cà phê ngắm cảnh Đà Lạt 2 ngày cuối tuần" },
            ].map((chip) => (
              <button
                key={chip.label}
                type="button"
                className="chip"
                onClick={() => {
                  setContext(chip.prompt);
                  if (inputRef.current) {
                    inputRef.current.focus();
                  }
                }}
                disabled={busy}
                style={{ fontSize: "12.5px", padding: "6px 12px", borderRadius: "999px" }}
              >
                {chip.label}
              </button>
            ))}
          </div>
        )}
        <div className="chat-box chat-input-shell">
          <span className="chat-input-icon" aria-hidden="true">
            ⌕
          </span>
          <input
            id="planner-context"
            ref={inputRef}
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
          {waitNotice ?? t(statusKey)}
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
