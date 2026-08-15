"use client";

import Script from "next/script";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { API_URL } from "@/lib/api";

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize(options: {client_id:string;callback:(response:{credential:string})=>void}):void;
      renderButton(element:HTMLElement, options:Record<string,unknown>):void;
    }}};
  }
}

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
const LOCAL = process.env.NODE_ENV !== "production" &&
  (process.env.NEXT_PUBLIC_APP_ENV ?? "local") === "local";

export default function Login() {
  const {locale,t}=useLocale();
  const [consent, setConsent] = useState(false);
  const [message, setMessage] = useState("");
  const [googleReady, setGoogleReady] = useState(false);
  const [busy,setBusy]=useState(false);
  const busyRef=useRef(false);
  const consentRef=useRef(false);
  const mountedRef=useRef(false);
  const buttonRef = useRef<HTMLDivElement>(null);

  useEffect(()=>{mountedRef.current=true;return()=>{mountedRef.current=false}},[]);

  const submitToken = useCallback(async (credential: string) => {
    if(busyRef.current||!consentRef.current)return;
    busyRef.current=true;
    setBusy(true);setMessage("");
    try{const storedSession=localStorage.getItem("ma_phien");const ma_phien=storedSession&&/^[0-9a-f-]{36}$/i.test(storedSession)?storedSession:crypto.randomUUID();
      localStorage.setItem("ma_phien", ma_phien);
      const response = await fetch(`${API_URL}/api/auth/oauth`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "google", token: credential, ma_phien, consent: true }),
      });
      const data = await response.json();
      if (!response.ok||typeof data.token!=="string"||!data.token.trim()||!consentRef.current) throw new Error("login failed");
      if(!mountedRef.current)return;
      localStorage.setItem("auth_token", data.token);
      location.href = "/history";
    }catch{if(mountedRef.current){setMessage(t("loginFailed"));busyRef.current=false;setBusy(false)}}
  }, [t]);

  useEffect(() => {
    if (!googleReady || !consent || !CLIENT_ID || !buttonRef.current || !window.google) return;
    buttonRef.current.replaceChildren();
    try{window.google.accounts.id.initialize({ client_id: CLIENT_ID, callback: response => submitToken(response.credential) });
      window.google.accounts.id.renderButton(buttonRef.current, { theme: "outline", size: "large", width: 360, locale });
    }catch{setMessage(t("loginFailed"))}
  }, [consent, googleReady, locale, submitToken,t]);

  function updateConsent(value:boolean){consentRef.current=value;setConsent(value)}

  return <main className="card login-card">
    {CLIENT_ID && <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onLoad={() => setGoogleReady(true)} onError={()=>setMessage(t("loginFailed"))}/>} 
    <div className="eyebrow">{t("accountEyebrow")}</div>
    <h1>{t("loginTitle")}</h1>
    <p className="lead">{t("loginLead")}</p>
    <label className="consent"><input type="checkbox" checked={consent} disabled={busy} onChange={event => updateConsent(event.target.checked)}/> <span>{t("consentBefore")} <Link href="/terms">{t("termsLabel")}</Link> {t("consentBetween")} <Link href="/privacy">{t("privacyLabel")}</Link> {t("consentAfter")}</span></label>
    {!consent && <p className="disclaimer" role="status">{t("consentRequired")}</p>}
    {consent && CLIENT_ID && <div ref={buttonRef} className="google-button" aria-busy={busy} style={{pointerEvents:busy?"none":"auto",opacity:busy?.6:1}}/>}
    {consent && LOCAL && !CLIENT_ID && <button className="primary form-submit" disabled={busy} onClick={() => submitToken("local-google-user")}>{t("continueGoogle")}</button>}
    {!LOCAL && !CLIENT_ID && <p className="error" role="alert">{t("loginNotConfigured")}</p>}
    {message && <p className="error" role="alert">{message}</p>}
  </main>;
}
