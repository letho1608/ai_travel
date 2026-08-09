"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useLocale } from "@/components/LocaleProvider";
import { API_URL } from "@/lib/api";
import { getSession } from "@/lib/session";
import type { Plan } from "@/lib/types";

type StoredPlan={token:string;ke_hoach:Plan};
type Notification={id:string;loai:"trip_24h";noi_dung:string;da_doc:boolean;plan_title?:string};

const isStoredPlan=(value:unknown):value is StoredPlan=>{if(!value||typeof value!=="object")return false;const item=value as Record<string,unknown>;return typeof item.token==="string"&&!!item.ke_hoach&&typeof item.ke_hoach==="object"&&typeof (item.ke_hoach as Record<string,unknown>).tieu_de==="string"};
const isNotification=(value:unknown):value is Notification=>{if(!value||typeof value!=="object")return false;const item=value as Record<string,unknown>;return typeof item.id==="string"&&item.loai==="trip_24h"&&typeof item.noi_dung==="string"&&typeof item.da_doc==="boolean"&&(item.plan_title===undefined||typeof item.plan_title==="string")};

export default function History() {
  const {t}=useLocale();
  const [plans,setPlans]=useState<StoredPlan[]>([]);
  const [notifications,setNotifications]=useState<Notification[]>([]);
  const [plansLoading,setPlansLoading]=useState(true);
  const [notificationsLoading,setNotificationsLoading]=useState(true);
  const [planError,setPlanError]=useState(false);
  const [notificationError,setNotificationError]=useState(false);
  const [mutationError,setMutationError]=useState(false);
  const [pending,setPending]=useState<Set<string>>(new Set());
  const pendingRef=useRef(new Set<string>());
  useEffect(() => {
    const controller=new AbortController();
    const session = getSession();
    const token = localStorage.getItem("auth_token") ?? "";
    const headers={"X-Session-Id":session,Authorization:`Bearer ${token}`};
    fetch(`${API_URL}/api/plans`,{headers,signal:controller.signal})
      .then(async (response) => {
        const data = await response.json();
        if(!response.ok||!Array.isArray(data.ds_ke_hoach)||!data.ds_ke_hoach.every(isStoredPlan))throw new Error("invalid plans response");
        setPlans(data.ds_ke_hoach);
      })
      .catch(error=>{if(error.name!=="AbortError")setPlanError(true)})
      .finally(()=>{if(!controller.signal.aborted)setPlansLoading(false)});
    fetch(`${API_URL}/api/notifications`,{headers,signal:controller.signal})
      .then(async response=>{const data=await response.json();if(!response.ok||!Array.isArray(data.items)||!data.items.every(isNotification))throw new Error("invalid notifications response");setNotifications(data.items)})
      .catch(error=>{if(error.name!=="AbortError")setNotificationError(true)})
      .finally(()=>{if(!controller.signal.aborted)setNotificationsLoading(false)});
    return()=>controller.abort();
  },[]);
  async function markRead(item:Notification){
    if(pendingRef.current.has(item.id))return;
    pendingRef.current.add(item.id);
    setPending(values=>new Set(values).add(item.id));setMutationError(false);
    try{const session=getSession();const token=localStorage.getItem("auth_token")||"";const response=await fetch(`${API_URL}/api/notifications/${item.id}`,{method:"PATCH",headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},body:JSON.stringify({ma_phien:session})});if(!response.ok)throw new Error("mark read failed");setNotifications(values=>values.map(value=>value.id===item.id?{...value,da_doc:true}:value))}catch{setMutationError(true)}finally{pendingRef.current.delete(item.id);setPending(values=>{const next=new Set(values);next.delete(item.id);return next})}
  }
  const planMessage=plansLoading?t("loading"):planError?t("loadFailed"):"";
  const showEmpty=!plansLoading&&!planError&&plans.length===0;
  const busy=plansLoading||notificationsLoading;
  return <main aria-busy={busy}><div className="eyebrow">{t("trips")}</div><h1>{t("historyTitle")}</h1>{notifications.length>0&&<section className="notification-list"><h2>{t("notifications")}</h2>{notifications.map(item=><article className={`card notification ${item.da_doc?"read":""}`} key={item.id}><span>{t("tripTomorrow",{title:item.plan_title||t("trips")})}</span>{!item.da_doc&&<button className="secondary" disabled={pending.has(item.id)} onClick={()=>markRead(item)}>{t("markRead")}</button>}</article>)}</section>}<div role="status" aria-live="polite">{planMessage&&<p className="lead">{planMessage}</p>}{notificationsLoading&&!plansLoading&&<p className="lead">{t("loading")}</p>}{notificationError&&<p className="error">{t("notificationsFailed")}</p>}{mutationError&&<p className="error">{t("markReadFailed")}</p>}</div>{showEmpty&&<section className="empty-state"><div className="empty-art" aria-hidden="true"/><h2>{t("noTrips")}</h2><p className="lead">{t("historyTitle")}</p><a className="primary" href="/">{t("createPlan")}</a></section>}<div className="timeline">{plans.map(item=><Link className="card" href={`/plan/${item.token}`} key={item.token}><strong>{item.ke_hoach.tieu_de}</strong><p>{item.ke_hoach.tom_tat}</p></Link>)}</div></main>;
}
