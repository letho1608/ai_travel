"use client";

import Script from "next/script";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { API_URL } from "@/lib/api";

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize(options: {client_id:string;callback:(response:{credential:string})=>void}):void;
      renderButton(element:HTMLElement, options:Record<string,unknown>):void;
      prompt?: () => void;
    }}};
  }
}

const CLIENT_ID = (process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "").trim();
const LOCAL = process.env.NODE_ENV !== "production" &&
  (process.env.NEXT_PUBLIC_APP_ENV ?? "local") === "local";
const ALLOW_MOCK = LOCAL && process.env.NEXT_PUBLIC_GOOGLE_MOCK === "1";

type Mode = "signin" | "signup" | "forgot";

function apiError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const detail = (data as {detail?: unknown}).detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap(item => {
      if (!item || typeof item !== "object" || !("msg" in item)) return [];
      const msg = (item as {msg?: unknown}).msg;
      return typeof msg === "string" ? [msg.replace(/^Value error,\s*/i, "")] : [];
    });
    if (messages.length) return messages.join(" ");
  }
  return fallback;
}

function EyeIcon({open}:{open:boolean}) {
  return open
    ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6A2 2 0 0 0 12 14a2 2 0 0 0 1.4-.6M9.9 5.1A10.6 10.6 0 0 1 12 5c5 0 9.3 3.1 11 7.5a12.7 12.7 0 0 1-4.2 5.1M6.7 6.7A12.7 12.7 0 0 0 1 12.5C2.7 16.9 7 20 12 20c1.4 0 2.7-.2 4-.7"/></svg>
    : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M1 12.5C2.7 8.1 7 5 12 5s9.3 3.1 11 7.5C21.3 16.9 17 20 12 20S2.7 16.9 1 12.5Z"/><circle cx="12" cy="12.5" r="3.2"/></svg>;
}

function GoogleMark() {
  return <svg viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5a5.6 5.6 0 0 1-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.7Z"/>
    <path fill="#34A853" d="M12 24c3.2 0 5.9-1 7.9-2.8l-3.9-3c-1.1.7-2.5 1.2-4 1.2-3.1 0-5.7-2.1-6.6-4.9H1.4v3.1A12 12 0 0 0 12 24Z"/>
    <path fill="#FBBC05" d="M5.4 14.5A7.2 7.2 0 0 1 5 12c0-.9.2-1.7.4-2.5V6.4H1.4A12 12 0 0 0 0 12c0 1.9.5 3.8 1.4 5.6l4-3.1Z"/>
    <path fill="#EA4335" d="M12 4.8c1.7 0 3.3.6 4.5 1.8l3.4-3.4C17.9 1.1 15.2 0 12 0A12 12 0 0 0 1.4 6.4l4 3.1C6.3 6.8 8.9 4.8 12 4.8Z"/>
  </svg>;
}

export default function Login() {
  const {locale,t}=useLocale();
  const [mode, setMode] = useState<Mode>("signin");
  const [message, setMessage] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [marketing, setMarketing] = useState(false);
  const [ageOk, setAgeOk] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const [busy,setBusy]=useState(false);
  const busyRef=useRef(false);
  const mountedRef=useRef(false);
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(()=>{mountedRef.current=true;return()=>{mountedRef.current=false}},[]);

  const sessionId = useCallback(() => {
    const stored = localStorage.getItem("ma_phien");
    const ma_phien = stored && /^[0-9a-f-]{36}$/i.test(stored) ? stored : crypto.randomUUID();
    localStorage.setItem("ma_phien", ma_phien);
    return ma_phien;
  }, []);

  const finishLogin = useCallback((token: string) => {
    if (!mountedRef.current) return;
    localStorage.setItem("auth_token", token);
    location.href = "/history";
  }, []);

  const submitToken = useCallback(async (credential: string) => {
    if (busyRef.current) return;
    if (mode === "signup" && !ageOk) {
      setMessage(t("ageRequired"));
      return;
    }
    busyRef.current=true;
    setBusy(true);setMessage("");
    try {
      const response = await fetch(`${API_URL}/api/auth/oauth`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "google", token: credential, ma_phien: sessionId(), consent: true }),
      });
      const data = await response.json();
      if (!response.ok||typeof data.token!=="string"||!data.token.trim()) {
        throw new Error(apiError(data, t("loginFailed")));
      }
      finishLogin(data.token);
    } catch(error) {
      if (mountedRef.current) {
        setMessage(error instanceof Error && error.message ? error.message : t("loginFailed"));
        busyRef.current=false;setBusy(false);
      }
    }
  }, [ageOk, finishLogin, mode, sessionId, t]);

  useEffect(() => {
    if (!googleReady || !CLIENT_ID || !buttonRef.current || !window.google || mode === "forgot") return;
    buttonRef.current.replaceChildren();
    try {
      window.google.accounts.id.initialize({ client_id: CLIENT_ID, callback: response => submitToken(response.credential) });
      window.google.accounts.id.renderButton(buttonRef.current, {
        type: "icon", shape: "circle", size: "large", theme: "outline", locale,
      });
    } catch { setMessage(t("loginFailed")); }
  }, [googleReady, locale, mode, submitToken, t]);

  function switchMode(next: Mode) {
    setMode(next);
    setMessage("");
    setPassword("");
    setConfirmPassword("");
    setShowPassword(false);
    setShowConfirm(false);
  }

  function strongPassword(value: string) {
    return value.length >= 8 && /[A-Za-z]/.test(value) && /\d/.test(value);
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    if (busyRef.current) return;
    const cleanUsername = username.trim().toLowerCase();
    if (!/^[A-Za-z0-9_.-]{3,40}$/.test(cleanUsername) || !strongPassword(password)) {
      setMessage(t("passwordRule"));
      return;
    }
    if (mode === "signup") {
      if (password !== confirmPassword) {
        setMessage(t("passwordMismatch"));
        return;
      }
      if (!ageOk) {
        setMessage(t("ageRequired"));
        return;
      }
      const digits = phone.replace(/\D/g, "").replace(/^84/, "").replace(/^0/, "");
      if (digits.length < 9 || digits.length > 10) {
        setMessage(t("phoneRule"));
        return;
      }
    }
    busyRef.current = true;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/api/auth/password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: cleanUsername,
          password,
          hanh_dong: mode === "signup" ? "dang_ky" : "dang_nhap",
          so_dien_thoai: mode === "signup" ? phone : undefined,
          ma_phien: sessionId(),
          consent: true,
        }),
      });
      const data = await response.json();
      if (!response.ok || typeof data.token !== "string" || !data.token.trim()) {
        throw new Error(apiError(data, t("loginFailed")));
      }
      finishLogin(data.token);
    } catch (error) {
      if (mountedRef.current) {
        setMessage(error instanceof Error && error.message ? error.message : t("loginFailed"));
        busyRef.current = false;
        setBusy(false);
      }
    }
  }

  async function submitForgot(event: FormEvent) {
    event.preventDefault();
    if (busyRef.current) return;
    const cleanUsername = username.trim().toLowerCase();
    if (!/^[A-Za-z0-9_.-]{3,40}$/.test(cleanUsername)) {
      setMessage(t("passwordRule"));
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${API_URL}/api/auth/password/forgot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: cleanUsername, ma_phien: sessionId() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(apiError(data, t("loginFailed")));
      setMessage(t("forgotSent"));
    } catch (error) {
      setMessage(error instanceof Error && error.message ? error.message : t("loginFailed"));
    } finally {
      if (mountedRef.current) {
        busyRef.current = false;
        setBusy(false);
      }
    }
  }

  function startGoogle() {
    if (busy) return;
    if (ALLOW_MOCK && !CLIENT_ID) {
      submitToken("mock-google-local-user");
      return;
    }
    if (!CLIENT_ID) {
      setMessage(t("loginNotConfigured"));
      return;
    }
    window.google?.accounts.id.prompt?.();
  }

  const gisClickable = Boolean(CLIENT_ID && googleReady && !busy);
  const googleControl = (
    <div className="google-wrap">
      <button type="button" className="google-icon-btn" disabled={busy} onClick={startGoogle} aria-label={t("continueGoogle")} style={{pointerEvents:gisClickable?"none":"auto",opacity:busy?.6:1}}>
        <GoogleMark/>
      </button>
      {CLIENT_ID && <div ref={buttonRef} className="google-icon-slot" aria-hidden="true" style={{pointerEvents:busy?"none":"auto"}}/>}
    </div>
  );

  return <main className="auth-page">
    {CLIENT_ID && <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onLoad={() => setGoogleReady(true)} onError={()=>setMessage(t("loginFailed"))}/>}
    <section className="auth-modal">
      {mode === "signin" && <>
        <h1>{t("signInTitle")}</h1>
        <p className="auth-switch">{t("newToApp")} <button type="button" onClick={() => switchMode("signup")}>{t("signUpLink")}</button></p>
        <form className="auth-form" onSubmit={submitPassword}>
          <input autoComplete="username" value={username} disabled={busy} minLength={3} maxLength={40} onChange={event=>setUsername(event.target.value)} placeholder={t("usernamePlaceholder")} required/>
          <label className="auth-password">
            <input autoComplete="current-password" type={showPassword?"text":"password"} value={password} disabled={busy} minLength={8} onChange={event=>setPassword(event.target.value)} placeholder={t("passwordLabel")} required/>
            <button type="button" className="auth-eye" onClick={()=>setShowPassword(value=>!value)} aria-label={showPassword?t("hidePassword"):t("showPassword")}><EyeIcon open={showPassword}/></button>
          </label>
          <button className="auth-submit" disabled={busy}>{t("continueButton")}</button>
        </form>
        <button type="button" className="auth-forgot" onClick={() => switchMode("forgot")}>{t("forgotPassword")}</button>
        <div className="auth-divider"><span>{t("orDivider")}</span></div>
        <div className="auth-social">{googleControl}</div>
        <p className="auth-legal">{t("signInLegal")} <Link href="/terms">{t("termsLabel")}</Link> {t("consentBetween")} <Link href="/privacy">{t("privacyLabel")}</Link>.</p>
      </>}
      {mode === "signup" && <>
        <h1>{t("signUpTitle")}</h1>
        <form className="auth-form" onSubmit={submitPassword}>
          <input autoComplete="username" value={username} disabled={busy} minLength={3} maxLength={40} onChange={event=>setUsername(event.target.value)} placeholder={t("usernamePlaceholder")} required/>
          <label className="auth-password">
            <input autoComplete="new-password" type={showPassword?"text":"password"} value={password} disabled={busy} minLength={8} onChange={event=>setPassword(event.target.value)} placeholder={t("passwordLabel")} required/>
            <button type="button" className="auth-eye" onClick={()=>setShowPassword(value=>!value)} aria-label={showPassword?t("hidePassword"):t("showPassword")}><EyeIcon open={showPassword}/></button>
          </label>
          <label className="auth-password">
            <input autoComplete="new-password" type={showConfirm?"text":"password"} value={confirmPassword} disabled={busy} minLength={8} onChange={event=>setConfirmPassword(event.target.value)} placeholder={t("confirmPasswordPlaceholder")} required/>
            <button type="button" className="auth-eye" onClick={()=>setShowConfirm(value=>!value)} aria-label={showConfirm?t("hidePassword"):t("showPassword")}><EyeIcon open={showConfirm}/></button>
          </label>
          <div className="auth-phone" aria-label={t("phoneLabel")}>
            <span className="auth-phone-prefix">
              <span className="vn-flag" aria-hidden="true"/>
              +84
            </span>
            <input inputMode="numeric" autoComplete="tel-national" value={phone} disabled={busy} onChange={event=>setPhone(event.target.value)} placeholder={t("phonePlaceholder")} required/>
          </div>
          <label className="auth-check"><input type="checkbox" checked={marketing} disabled={busy} onChange={event=>setMarketing(event.target.checked)}/> <span>{t("marketingOptIn")} <Link href="/privacy">{t("learnMore")}</Link></span></label>
          <label className="auth-check"><input type="checkbox" checked={ageOk} disabled={busy} onChange={event=>setAgeOk(event.target.checked)} required/> <span>{t("ageConfirm")}</span></label>
          <button className="auth-submit" disabled={busy}>{t("signUpButton")}</button>
        </form>
        <p className="auth-switch">{t("alreadyHaveAccount")} <button type="button" onClick={() => switchMode("signin")}>{t("signInTitle")}</button></p>
        <div className="auth-divider"><span>{t("orDivider")}</span></div>
        <div className="auth-social">{googleControl}</div>
      </>}
      {mode === "forgot" && <>
        <h1>{t("forgotPassword")}</h1>
        <p className="auth-copy">{t("forgotLead")}</p>
        <form className="auth-form" onSubmit={submitForgot}>
          <input autoComplete="username" value={username} disabled={busy} minLength={3} maxLength={40} onChange={event=>setUsername(event.target.value)} placeholder={t("usernamePlaceholder")} required/>
          <button className="auth-submit" disabled={busy}>{t("continueButton")}</button>
        </form>
        <p className="auth-switch"><button type="button" onClick={() => switchMode("signin")}>{t("forgotBack")}</button></p>
      </>}
      {message && <p className="error" role="alert">{message}</p>}
    </section>
  </main>;
}
