"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { API_URL } from "@/lib/api";
import type { Locale } from "@/lib/i18n-core";

type Currency="VND"|"USD"|"EUR"|"GBP"|"JPY"|"KRW"|"THB";
type Unit="metric"|"imperial";
type Preferences={ngon_ngu:Locale;tien_te:Currency;don_vi:Unit};
type MessageKey="settingsSaved"|"deleteLoginRequired"|"deleteFailed"|"preferencesLoadFailed"|"preferencesSaveFailed";
type Message={key:MessageKey;error:boolean}|null;

const defaults:Preferences={ngon_ngu:"vi",tien_te:"VND",don_vi:"metric"};
const languages:ReadonlyArray<readonly[Locale,string]>=[["vi","Tiếng Việt"],["en","English"],["ar","العربية"],["bg","Български"],["de","Deutsch"],["es","Español"],["fr","Français"],["he","עברית"],["hi","हिन्दी"],["it","Italiano"],["ja","日本語"],["nl","Nederlands"],["pl","Polski"],["pt","Português"],["ru","Русский"],["tr","Türkçe"],["zh","中文"],["ko","한국어"],["th","ไทย"]];
const currencies:Currency[]=["VND","USD","EUR","GBP","JPY","KRW","THB"];
const isPreferences=(value:unknown):value is Preferences=>{if(!value||typeof value!=="object")return false;const item=value as Record<string,unknown>;return languages.some(([code])=>code===item.ngon_ngu)&&currencies.includes(item.tien_te as Currency)&&(item.don_vi==="metric"||item.don_vi==="imperial")};
async function fetchWithTimeout(url:string,init:RequestInit={}){const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),15000);try{return await fetch(url,{...init,signal:controller.signal})}finally{clearTimeout(timeout)}}

export default function Settings(){
  const {t}=useLocale();
  const [values,setValues]=useState<Preferences>(defaults);
  const [message,setMessage]=useState<Message>(null);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [confirming,setConfirming]=useState(false);
  const [confirmation,setConfirmation]=useState("");
  const busyRef=useRef(false);

  useEffect(()=>{const controller=new AbortController();const timeout=setTimeout(()=>{controller.abort();setMessage({key:"preferencesLoadFailed",error:true});setLoading(false)},15000);const session=localStorage.getItem("ma_phien");const auth=localStorage.getItem("auth_token");if(!session&&!auth){clearTimeout(timeout);setLoading(false);return()=>controller.abort()};fetch(`${API_URL}/api/auth/preferences`,{headers:{...(session?{"X-Session-Id":session}:{}),...(auth?{Authorization:`Bearer ${auth}`}:{})},signal:controller.signal}).then(async response=>{if(response.status===401){try{localStorage.removeItem("auth_token")}catch{}throw new Error("unauthorized")}const data=await response.json();if(!response.ok||!isPreferences(data))throw new Error("invalid preferences");setValues(data);localStorage.setItem("travel_preferences",JSON.stringify(data));window.dispatchEvent(new Event("travel-preferences-changed"))}).catch(error=>{if(error.name!=="AbortError")setMessage({key:"preferencesLoadFailed",error:true})}).finally(()=>{clearTimeout(timeout);if(!controller.signal.aborted)setLoading(false)});return()=>{clearTimeout(timeout);controller.abort()}},[]);

  async function save(event:FormEvent){event.preventDefault();if(busyRef.current)return;busyRef.current=true;setBusy(true);setMessage(null);try{let session=localStorage.getItem("ma_phien");if(!session){session=crypto.randomUUID();localStorage.setItem("ma_phien",session)}const auth=localStorage.getItem("auth_token");const response=await fetchWithTimeout(`${API_URL}/api/auth/preferences`,{method:"PUT",headers:{"Content-Type":"application/json",...(auth?{Authorization:`Bearer ${auth}`}:{})},body:JSON.stringify({...values,ma_phien:session})});if(response.status===401){try{localStorage.removeItem("auth_token")}catch{}throw new Error("unauthorized")}const data=await response.json();if(!response.ok||!isPreferences(data))throw new Error("save failed");setValues(data);localStorage.setItem("travel_preferences",JSON.stringify(data));window.dispatchEvent(new Event("travel-preferences-changed"));setMessage({key:"settingsSaved",error:false})}catch{setMessage({key:"preferencesSaveFailed",error:true})}finally{busyRef.current=false;setBusy(false)}}

  async function deleteAccount(){if(busyRef.current||confirmation!=="XOA TAI KHOAN")return;const auth=localStorage.getItem("auth_token");if(!auth)return setMessage({key:"deleteLoginRequired",error:true});busyRef.current=true;setBusy(true);setMessage(null);try{const response=await fetch(`${API_URL}/api/auth/account`,{method:"DELETE",headers:{"Content-Type":"application/json",Authorization:`Bearer ${auth}`},body:JSON.stringify({confirmation})});if(!response.ok)throw new Error("delete failed");for(const key of ["auth_token","travel_preferences","ma_phien"]){try{localStorage.removeItem(key)}catch{}}location.assign("/")}catch{setMessage({key:"deleteFailed",error:true});busyRef.current=false;setBusy(false)}}

  return <main className="settings-page card" aria-busy={loading||busy}><div className="eyebrow">{t("personalOptions")}</div><h1>{t("settingsTitle")}</h1><div aria-live="polite">{loading&&<p className="status">{t("loading")}</p>}{message&&<p className={message.error?"error":"status"} role={message.error?"alert":"status"}>{t(message.key)}</p>}</div><form onSubmit={save}><label>{t("languageLabel")}<select disabled={loading||busy} value={values.ngon_ngu} onChange={event=>setValues({...values,ngon_ngu:event.target.value as Locale})}>{languages.map(([code,label])=><option value={code} key={code}>{label}</option>)}</select></label><label>{t("currencyLabel")}<select disabled={loading||busy} value={values.tien_te} onChange={event=>setValues({...values,tien_te:event.target.value as Currency})}>{currencies.map(value=><option key={value}>{value}</option>)}</select></label><label>{t("unitsLabel")}<select disabled={loading||busy} value={values.don_vi} onChange={event=>setValues({...values,don_vi:event.target.value as Unit})}><option value="metric">{t("metricLabel")}</option><option value="imperial">{t("imperialLabel")}</option></select></label><button className="primary" disabled={loading||busy}>{t("saveOptions")}</button></form><section className="danger-zone"><h2>{t("deleteData")}</h2><p>{t("deleteDescription")}</p>{confirming?<div role="group" aria-labelledby="delete-confirmation-label"><label id="delete-confirmation-label">{t("deletePrompt")}<input autoFocus value={confirmation} disabled={busy} onChange={event=>setConfirmation(event.target.value)}/></label><div><button className="danger" type="button" disabled={busy||confirmation!=="XOA TAI KHOAN"} onClick={deleteAccount}>{t("deleteAccount")}</button><button className="secondary" type="button" disabled={busy} onClick={()=>{setConfirming(false);setConfirmation("")}}>{t("cancel")}</button></div></div>:<button className="danger" type="button" disabled={loading||busy} onClick={()=>{setConfirming(true);setMessage(null)}}>{t("deleteAccount")}</button>}</section></main>;
}
