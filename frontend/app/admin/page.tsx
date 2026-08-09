"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { API_URL } from "@/lib/api";

type ProviderStatus = { name:string; mode:string; status:string; detail:string };
type BookingRequest = {
  id:string; offer_id:string; loai?:string; ghi_chu?:string; trang_thai:string;
  phu_trach?:string; provider_reference?:string; ngay_tao:string;
};
type CatalogPlace = {
  id:string; name:string; kind:string; area:string; lat:number; lng:number; cost:number;
  duration_min:number; tags:string[]; open_hour:number; close_hour:number; source:string;
  source_url?:string|null;
};
type AdminPlan = {
  token:string; session_id:string; user_id?:string|null; version:number; title:string;
  summary:string; departure_date?:string|null; duration?:string|null; people?:number|null;
  language:string; expires_at?:string|null;
};
type AdminUser = {
  id:string; email:string; name?:string|null; provider?:string|null;
  plans:number; comments:number; booking_requests:number; feedback:number; notifications:number;
};
type AiUsage = {
  id?:string; provider:string; model:string; input_tokens:number; output_tokens:number;
  cost_usd:number; success?:boolean; created_at?:string;
};
type AdminEvent = {ma_phien:string;su_kien:string;du_lieu:Record<string,unknown>;thoi_gian:string};
type ProviderDiagnostic = {
  ready:boolean; mode?:string; model?:string; base_url?:string;
  api_key_configured?:boolean; api_key_length?:number;
  client_id_configured?:boolean; client_secret_configured?:boolean;
  circuit_breaker?:{allowing_calls:boolean;state:string;recent_failures:number;remaining_open_seconds:number};
  required_env:string[]; next_action:string;
};
type AdminDashboard = {
  environment:string; ready:boolean;
  dependencies:Record<string,{name:string;status:string}>;
  providers:ProviderStatus[];
  provider_diagnostics:Record<string,ProviderDiagnostic>;
  limits:Record<string,number>;
  ai_quality:{mode:string;model:string;live_provider_ready:boolean;total_plans:number;fallback_plan_count:number;fallback_rate_percent:number;deterministic_mode:boolean;deterministic_plan_count:number;deterministic_rate_percent:number;next_action:string};
  catalog_quality:{
    metadata:Record<string,unknown>;
    distance_matrix:Record<string,unknown>;
    place_count:number;
    source_url_coverage_percent:number;
    missing_source_url:number;
    unusual_hours:number;
    kind_counts:Record<string,number>;
    source_counts:Record<string,number>;
    top_tags:Record<string,number>;
    failing_coverage:Record<string,unknown>[];
    sample_places:{id:string;name:string;kind:string;area:string;source:string;source_url?:string|null;open_hour:number;close_hour:number}[];
  };
  summary:Record<string,number>;
  recent_events:AdminEvent[];
  booking_requests:BookingRequest[];
};

const STATUS_LABELS:Record<string,string> = {
  requested:"Mới nhận", reviewing:"Đang kiểm tra", needs_customer:"Chờ khách",
  handed_off:"Đã chuyển provider", cancelled:"Đã hủy",
};
const OPEN_STATUSES=["requested","reviewing","needs_customer"];
const LIMIT_LABELS:Record<string,string> = {
  max_request_body_bytes:"Max request body",
};

export default function AdminPage(){
  const [token,setToken]=useState("");
  const [data,setData]=useState<AdminDashboard|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [assignee,setAssignee]=useState("");
  const [statusFilter,setStatusFilter]=useState("open");
  const [notes,setNotes]=useState<Record<string,string>>({});
  const [references,setReferences]=useState<Record<string,string>>({});
  const [pendingRequest,setPendingRequest]=useState<string|null>(null);
  const [lastLoaded,setLastLoaded]=useState<Date|null>(null);
  const [catalogQuery,setCatalogQuery]=useState("");
  const [catalogKind,setCatalogKind]=useState("");
  const [catalogArea,setCatalogArea]=useState("");
  const [catalogTag,setCatalogTag]=useState("");
  const [catalogItems,setCatalogItems]=useState<CatalogPlace[]>([]);
  const [catalogTotal,setCatalogTotal]=useState(0);
  const [catalogBusy,setCatalogBusy]=useState(false);
  const [catalogQualityBusy,setCatalogQualityBusy]=useState(false);
  const [catalogExportBusy,setCatalogExportBusy]=useState(false);
  const [planQuery,setPlanQuery]=useState("");
  const [plans,setPlans]=useState<AdminPlan[]>([]);
  const [planTotal,setPlanTotal]=useState(0);
  const [plansBusy,setPlansBusy]=useState(false);
  const [userQuery,setUserQuery]=useState("");
  const [users,setUsers]=useState<AdminUser[]>([]);
  const [userTotal,setUserTotal]=useState(0);
  const [usersBusy,setUsersBusy]=useState(false);
  const [aiUsage,setAiUsage]=useState<AiUsage[]>([]);
  const [aiUsageTotal,setAiUsageTotal]=useState(0);
  const [aiUsageBusy,setAiUsageBusy]=useState(false);
  const [aiQualityBusy,setAiQualityBusy]=useState(false);
  const [diagnosticsBusy,setDiagnosticsBusy]=useState(false);
  const [maintenanceBusy,setMaintenanceBusy]=useState(false);
  const aiLiveEnvSnippet="AI_MODE=groq\nAPI_KEY_GROQ=<your_groq_key>\nTEN_MODEL_GROQ=llama-3.3-70b-versatile\nAI_BASE_URL=https://api.groq.com/openai/v1";
  const [maintenanceMessage,setMaintenanceMessage]=useState("");
  const [eventQuery,setEventQuery]=useState("");
  const [events,setEvents]=useState<AdminEvent[]>([]);
  const [eventTotal,setEventTotal]=useState(0);
  const [eventsBusy,setEventsBusy]=useState(false);
  const visibleBookings=useMemo(()=>{
    const items=data?.booking_requests ?? [];
    if(statusFilter==="all")return items;
    if(statusFilter==="open")return items.filter(item=>OPEN_STATUSES.includes(item.trang_thai));
    return items.filter(item=>item.trang_thai===statusFilter);
  },[data,statusFilter]);

  useEffect(()=>{
    setToken(sessionStorage.getItem("admin_token")||sessionStorage.getItem("support_token")||"");
  },[]);

  async function load(event?:FormEvent){
    event?.preventDefault();
    setBusy(true); setError("");
    sessionStorage.setItem("admin_token",token);
    sessionStorage.setItem("support_token",token);
    try{
      const response=await fetch(`${API_URL}/api/admin/dashboard`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok) throw new Error(payload.detail||"Không tải được admin dashboard");
      setData(payload);
      setLastLoaded(new Date());
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tải được admin dashboard");
    }finally{setBusy(false)}
  }

  async function move(item:BookingRequest,status:string){
    const owner=assignee.trim();
    if(!owner){setError("Nhập tên nhân sự phụ trách trước khi cập nhật.");return}
    setPendingRequest(item.id); setError("");
    const response=await fetch(`${API_URL}/api/support/booking-requests/${item.id}`,{
      method:"PATCH",
      headers:{"Content-Type":"application/json","X-Support-Token":token},
      body:JSON.stringify({
        trang_thai:status,
        phu_trach:owner,
        ghi_chu_noi_bo:notes[item.id]?.trim()||"Cập nhật từ admin dashboard",
        provider_reference:status==="handed_off"?(references[item.id]?.trim()||null):null,
      }),
    });
    const payload=await response.json();
    if(!response.ok){
      setError(payload.detail||"Không cập nhật được yêu cầu");
      setPendingRequest(null);
      return;
    }
    setNotes(values=>({...values,[item.id]:""}));
    if(status==="handed_off")setReferences(values=>({...values,[item.id]:""}));
    await load();
    setPendingRequest(null);
  }

  function catalogParams(limit?:string){
    const params=new URLSearchParams();
    if(limit)params.set("limit",limit);
    if(catalogQuery.trim())params.set("q",catalogQuery.trim());
    if(catalogKind.trim())params.set("kind",catalogKind.trim());
    if(catalogArea.trim())params.set("area",catalogArea.trim());
    if(catalogTag.trim())params.set("tag",catalogTag.trim());
    return params;
  }

  async function exportCatalog(){
    setCatalogExportBusy(true); setError("");
    try{
      const params=catalogParams();
      const response=await fetch(`${API_URL}/api/admin/catalog/export.csv?${params}`,{
        headers:{"X-Admin-Token":token},
      });
      if(!response.ok){
        const payload=await response.json().catch(()=>null);
        throw new Error(payload?.detail||"Không xuất được catalog CSV");
      }
      const blob=await response.blob();
      const url=URL.createObjectURL(blob);
      const anchor=document.createElement("a");
      anchor.href=url;
      anchor.download="catalog-export.csv";
      anchor.click();
      setTimeout(()=>URL.revokeObjectURL(url),0);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không xuất được catalog CSV");
    }finally{setCatalogExportBusy(false)}
  }

  async function searchCatalog(event?:FormEvent){
    event?.preventDefault();
    setCatalogBusy(true); setError("");
    const params=catalogParams("30");
    try{
      const response=await fetch(`${API_URL}/api/admin/catalog?${params}`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không tìm được catalog");
      setCatalogItems(Array.isArray(payload.items)?payload.items:[]);
      setCatalogTotal(typeof payload.total==="number"?payload.total:0);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tìm được catalog");
    }finally{setCatalogBusy(false)}
  }

  async function refreshCatalogQuality(){
    if(!data)return;
    setCatalogQualityBusy(true); setError("");
    try{
      const response=await fetch(`${API_URL}/api/admin/catalog/quality`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không tải được data quality");
      setData(current=>current?{...current,catalog_quality:payload}:current);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tải được data quality");
    }finally{setCatalogQualityBusy(false)}
  }

  async function searchPlans(event?:FormEvent){
    event?.preventDefault();
    setPlansBusy(true); setError("");
    const params=new URLSearchParams({limit:"30"});
    if(planQuery.trim())params.set("q",planQuery.trim());
    try{
      const response=await fetch(`${API_URL}/api/admin/plans?${params}`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không tải được danh sách plan");
      setPlans(Array.isArray(payload.items)?payload.items:[]);
      setPlanTotal(typeof payload.total==="number"?payload.total:0);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tải được danh sách plan");
    }finally{setPlansBusy(false)}
  }

  async function searchUsers(event?:FormEvent){
    event?.preventDefault();
    setUsersBusy(true); setError("");
    const params=new URLSearchParams({limit:"30"});
    if(userQuery.trim())params.set("q",userQuery.trim());
    try{
      const response=await fetch(`${API_URL}/api/admin/users?${params}`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không tải được danh sách user");
      setUsers(Array.isArray(payload.items)?payload.items:[]);
      setUserTotal(typeof payload.total==="number"?payload.total:0);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tải được danh sách user");
    }finally{setUsersBusy(false)}
  }

  function maskUserId(id:string){
    return id.length>12?`${id.slice(0,8)}...${id.slice(-4)}`:id;
  }

  async function loadAiUsage(){
    setAiUsageBusy(true); setError("");
    try{
      const response=await fetch(`${API_URL}/api/admin/ai-usage?limit=30`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không tải được AI usage");
      setAiUsage(Array.isArray(payload.items)?payload.items:[]);
      setAiUsageTotal(typeof payload.total==="number"?payload.total:0);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tải được AI usage");
    }finally{setAiUsageBusy(false)}
  }

  async function refreshAiQuality(){
    if(!data)return;
    setAiQualityBusy(true); setError("");
    try{
      const response=await fetch(`${API_URL}/api/admin/ai-quality`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không tải được AI quality");
      setData(current=>current?{...current,ai_quality:payload}:current);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tải được AI quality");
    }finally{setAiQualityBusy(false)}
  }

  function copyAiLiveEnvSnippet(){
    void navigator.clipboard?.writeText(aiLiveEnvSnippet);
  }

  async function loadEvents(event?:FormEvent){
    event?.preventDefault();
    setEventsBusy(true); setError("");
    const params=new URLSearchParams({limit:"50"});
    if(eventQuery.trim())params.set("q",eventQuery.trim());
    try{
      const response=await fetch(`${API_URL}/api/admin/events?${params}`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không tải được event audit log");
      setEvents(Array.isArray(payload.items)?payload.items:[]);
      setEventTotal(typeof payload.total==="number"?payload.total:0);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không tải được event audit log");
    }finally{setEventsBusy(false)}
  }

  async function cleanupExpired(){
    setMaintenanceBusy(true); setError(""); setMaintenanceMessage("");
    try{
      const response=await fetch(`${API_URL}/api/admin/maintenance/cleanup-expired`,{
        method:"POST",
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không chạy được cleanup");
      setMaintenanceMessage(`Removed ${typeof payload.removed_plans==="number"?payload.removed_plans:0} expired plans.`);
      await load();
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không chạy được cleanup");
    }finally{setMaintenanceBusy(false)}
  }

  async function refreshDiagnostics(){
    if(!data)return;
    setDiagnosticsBusy(true); setError("");
    try{
      const response=await fetch(`${API_URL}/api/admin/providers/diagnostics`,{
        headers:{"X-Admin-Token":token},
      });
      const payload=await response.json();
      if(!response.ok)throw new Error(payload.detail||"Không kiểm tra được provider");
      setData(current=>current?{...current,provider_diagnostics:payload}:current);
    }catch(reason){
      setError(reason instanceof Error?reason.message:"Không kiểm tra được provider");
    }finally{setDiagnosticsBusy(false)}
  }

  return <main className="admin-page">
    <div className="eyebrow">Admin console</div>
    <h1>Quản lý hệ thống</h1>
    <p className="lead">Theo dõi dữ liệu, AI, provider, chi phí và hàng đợi hỗ trợ booking trong một màn hình riêng cho admin.</p>

    <form className="card admin-login" onSubmit={load}>
      <label>Admin token<input type="password" value={token} onChange={event=>setToken(event.target.value)} autoComplete="current-password" required/></label>
      <button className="primary" disabled={busy}>{busy?"Đang tải...":"Mở dashboard"}</button>
    </form>
    {error&&<p className="error" role="alert">{error}</p>}

    {data&&<>
      <section className="admin-strip">
        <article className="card"><span>Environment</span><strong>{data.environment}</strong><small>{data.ready?"Ready":"Cần kiểm tra"}</small></article>
        <article className="card"><span>Plans</span><strong>{data.summary.plans}</strong><small>{data.summary.comments} comments</small></article>
        <article className="card"><span>AI cost today</span><strong>${data.summary.daily_ai_cost_usd.toFixed(4)}</strong><small>{data.summary.ai_calls} AI calls</small></article>
        <article className="card"><span>AI deterministic</span><strong>{data.ai_quality.deterministic_rate_percent}%</strong><small>{data.ai_quality.deterministic_plan_count}/{data.ai_quality.total_plans} plans</small></article>
        <article className="card"><span>Open support</span><strong>{data.summary.open_booking_requests}</strong><small>{data.summary.booking_requests} total</small></article>
      </section>

      <section className="admin-grid">
        <div className="card">
          <div className="panel-title">Provider readiness</div>
          <div className="admin-list">
            {data.providers.map(provider=><article key={provider.name}>
              <div><strong>{provider.name}</strong><small>{provider.mode}</small></div>
              <span className={`admin-pill ${provider.status}`}>{provider.status}</span>
              <p>{provider.detail}</p>
            </article>)}
          </div>
        </div>

        <div className="card admin-provider-diagnostics">
          <div className="admin-section-head">
            <div className="panel-title">Provider diagnostics</div>
            <button type="button" className="secondary" onClick={refreshDiagnostics} disabled={diagnosticsBusy}>{diagnosticsBusy?"Checking...":"Check"}</button>
          </div>
          <div className="admin-diagnostic-list">
            {Object.entries(data.provider_diagnostics).map(([key,item])=><article key={key}>
              <div><strong>{key.toUpperCase()}</strong><span className={`admin-pill ${item.ready?"ready":"missing_credentials"}`}>{item.ready?"ready":"needs setup"}</span></div>
              <p>{item.next_action}</p>
              <small>{[item.mode,item.model,item.base_url].filter(Boolean).join(" - ")}</small>
              {item.circuit_breaker&&<small>circuit: {item.circuit_breaker.state} - failures {item.circuit_breaker.recent_failures} - retry {item.circuit_breaker.remaining_open_seconds}s</small>}
              <div className="admin-tags">{item.required_env.map(env=><span key={env}>{env}</span>)}</div>
            </article>)}
          </div>
        </div>

        <div className="card">
          <div className="panel-title">System counters</div>
          <div className="metric-grid">
            {Object.entries(data.summary).map(([key,value])=><div key={key}><span>{key.replaceAll("_"," ")}</span><strong>{value}</strong></div>)}
          </div>
        </div>

        <div className="card">
          <div className="panel-title">Operational limits</div>
          <div className="metric-grid">
            {Object.entries(data.limits).map(([key,value])=><div key={key}><span>{LIMIT_LABELS[key]||key.replaceAll("_"," ")}</span><strong>{key.endsWith("_bytes")?`${Math.round(value/1024)} KB`:value}</strong></div>)}
          </div>
        </div>

        <div className="card">
          <div className="admin-section-head">
            <div className="panel-title">AI quality</div>
            <button type="button" className="secondary" onClick={refreshAiQuality} disabled={aiQualityBusy}>{aiQualityBusy?"Refreshing...":"Refresh quality"}</button>
          </div>
          <div className="metric-grid">
            <div><span>mode</span><strong>{data.ai_quality.mode}</strong></div>
            <div><span>model</span><strong>{data.ai_quality.model}</strong></div>
            <div><span>live provider</span><strong>{data.ai_quality.live_provider_ready?"ready":"not ready"}</strong></div>
            <div><span>fallback plans</span><strong>{data.ai_quality.fallback_plan_count}</strong></div>
            <div><span>deterministic plans</span><strong>{data.ai_quality.deterministic_plan_count}</strong></div>
          </div>
          <p className="disclaimer">{data.ai_quality.next_action}</p>
          {!data.ai_quality.live_provider_ready&&<div className="admin-env-snippet">
            <code>{aiLiveEnvSnippet}</code>
            <button type="button" className="secondary" onClick={copyAiLiveEnvSnippet}>Copy .env snippet</button>
          </div>}
        </div>
      </section>

      <section className="card admin-ai-usage">
        <div className="admin-section-head">
          <div>
            <div className="panel-title">AI usage</div>
            <p className="disclaimer">{aiUsageTotal} recent AI calls. Tracks model, token volume and cost without exposing prompts or API keys.</p>
          </div>
          <button type="button" className="secondary" onClick={loadAiUsage} disabled={aiUsageBusy}>{aiUsageBusy?"Loading...":"Load AI usage"}</button>
        </div>
        <div className="admin-ai-table">
          {aiUsage.map((item,index)=><article key={item.id||`${item.provider}-${index}`}>
            <div><strong>{item.provider}</strong><small>{item.model}</small></div>
            <span>{item.input_tokens} in</span>
            <span>{item.output_tokens} out</span>
            <span>${item.cost_usd.toFixed(6)}</span>
            <span className={`admin-pill ${item.success===false?"down":"ready"}`}>{item.success===false?"failed":"success"}</span>
            <span>{item.created_at?new Date(item.created_at).toLocaleString("vi-VN"):"n/a"}</span>
          </article>)}
          {aiUsage.length===0&&<p className="disclaimer">Bấm Load AI usage để xem lịch sử gọi AI gần đây.</p>}
        </div>
      </section>

      <section className="card admin-maintenance">
        <div className="admin-section-head">
          <div>
            <div className="panel-title">System maintenance</div>
            <p className="disclaimer">Manual run for the same safe cleanup job used by the hourly backend scheduler. It only removes expired anonymous plans and related orphan records.</p>
            {maintenanceMessage&&<p className="status">{maintenanceMessage}</p>}
          </div>
          <button type="button" className="secondary" onClick={cleanupExpired} disabled={maintenanceBusy||busy}>{maintenanceBusy?"Cleaning...":"Cleanup expired plans"}</button>
        </div>
      </section>

      <section className="card admin-data-quality">
        <div className="admin-section-head">
          <div className="panel-title">Data quality</div>
          <button type="button" className="secondary" onClick={refreshCatalogQuality} disabled={catalogQualityBusy}>
            {catalogQualityBusy?"Refreshing...":"Refresh quality"}
          </button>
        </div>
        <div className="admin-data-head">
          <article><span>Verified POI</span><strong>{data.catalog_quality.place_count}</strong><small>{String(data.catalog_quality.metadata.provider||"catalog")}</small></article>
          <article><span>Source URL</span><strong>{data.catalog_quality.source_url_coverage_percent}%</strong><small>{data.catalog_quality.missing_source_url} missing</small></article>
          <article><span>Distance matrix</span><strong>{data.catalog_quality.distance_matrix.loaded?"Ready":"Missing"}</strong><small>{String(data.catalog_quality.distance_matrix.profile||"n/a")}</small></article>
          <article><span>Hours issues</span><strong>{data.catalog_quality.unusual_hours}</strong><small>open/close validation</small></article>
        </div>
        <div className="admin-grid compact">
          <div>
            <strong>Place types</strong>
            <div className="admin-tags">{Object.entries(data.catalog_quality.kind_counts).map(([key,value])=><span key={key}>{key}: {value}</span>)}</div>
          </div>
          <div>
            <strong>Top tags</strong>
            <div className="admin-tags">{Object.entries(data.catalog_quality.top_tags).map(([key,value])=><span key={key}>{key}: {value}</span>)}</div>
          </div>
        </div>
        <div className="admin-place-table">
          {data.catalog_quality.sample_places.map(place=><article key={place.id}>
            <strong>{place.name}</strong><span>{place.kind}</span><span>{place.area}</span><span>{place.open_hour}:00-{place.close_hour}:00</span>{place.source_url?<a href={place.source_url} target="_blank" rel="noreferrer">source</a>:<em>missing source</em>}
          </article>)}
        </div>
        {data.catalog_quality.failing_coverage.length>0&&<p className="disclaimer">{data.catalog_quality.failing_coverage.length} coverage cells still need more places. Admin should import or curate these areas before expanding scope.</p>}
      </section>

      <section className="card admin-catalog-search">
        <div className="panel-title">Catalog search</div>
        <form className="admin-catalog-form" onSubmit={searchCatalog}>
          <label>Text<input value={catalogQuery} onChange={event=>setCatalogQuery(event.target.value)} placeholder="name, tag, source"/></label>
          <label>Kind<input value={catalogKind} onChange={event=>setCatalogKind(event.target.value)} placeholder="cafe, dia_danh"/></label>
          <label>Area<input value={catalogArea} onChange={event=>setCatalogArea(event.target.value)} placeholder="Hoàn Kiếm"/></label>
          <label>Tag<input value={catalogTag} onChange={event=>setCatalogTag(event.target.value)} placeholder="chill"/></label>
          <button className="primary" disabled={catalogBusy}>{catalogBusy?"Searching...":"Search"}</button>
          <button type="button" className="secondary" disabled={catalogExportBusy} onClick={exportCatalog}>{catalogExportBusy?"Exporting...":"Export CSV"}</button>
        </form>
        <p className="disclaimer">{catalogTotal} matching places. Results are read-only to protect provenance.</p>
        <div className="admin-place-table catalog">
          {catalogItems.map(place=><article key={place.id}>
            <strong>{place.name}</strong><span>{place.kind}</span><span>{place.area}</span><span>{place.open_hour}:00-{place.close_hour}:00</span>{place.source_url?<a href={place.source_url} target="_blank" rel="noreferrer">source</a>:<em>missing source</em>}
          </article>)}
          {catalogItems.length===0&&<p className="disclaimer">Nhập filter và bấm Search để xem catalog.</p>}
        </div>
      </section>

      <section className="card admin-plan-search">
        <div className="panel-title">Recent plans</div>
        <form className="admin-plan-form" onSubmit={searchPlans}>
          <label>Search token/session/title<input value={planQuery} onChange={event=>setPlanQuery(event.target.value)} placeholder="token, session, title"/></label>
          <button className="primary" disabled={plansBusy}>{plansBusy?"Loading...":"Load plans"}</button>
        </form>
        <p className="disclaimer">{planTotal} matching plans. Open links are read-only share views unless owner session is present.</p>
        <div className="admin-plan-table">
          {plans.map(plan=><article key={plan.token}>
            <div><strong>{plan.title||plan.token}</strong><small>{plan.summary}</small></div>
            <span>v{plan.version}</span><span>{plan.duration||"n/a"} · {plan.people||"?"} pax</span><span>{plan.language}</span><a href={`/plan/${plan.token}`}>Open</a>
          </article>)}
          {plans.length===0&&<p className="disclaimer">Bấm Load plans để xem các kế hoạch gần đây.</p>}
        </div>
      </section>

      <section className="card admin-user-search">
        <div className="panel-title">User management</div>
        <form className="admin-plan-form" onSubmit={searchUsers}>
          <label>Search email/name/id<input value={userQuery} onChange={event=>setUserQuery(event.target.value)} placeholder="email, name, user id"/></label>
          <button className="primary" disabled={usersBusy}>{usersBusy?"Loading...":"Load users"}</button>
        </form>
        <p className="disclaimer">{userTotal} matching users. Read-only view for safe account support and system monitoring.</p>
        <div className="admin-user-table">
          {users.map(user=><article key={user.id}>
            <div><strong>{user.email}</strong><small>{user.name||"No display name"} - {maskUserId(user.id)}</small></div>
            <span>{user.provider||"n/a"}</span>
            <span>{user.plans} plans</span>
            <span>{user.comments} comments</span>
            <span>{user.booking_requests} bookings</span>
            <span>{user.feedback} feedback</span>
            <span>{user.notifications} notices</span>
          </article>)}
          {users.length===0&&<p className="disclaimer">Bấm Load users để xem tài khoản và mức sử dụng.</p>}
        </div>
      </section>

      <section className="card admin-support">
        <div className="admin-section-head">
          <div>
            <div className="panel-title">Booking support queue</div>
            {lastLoaded&&<p className="disclaimer">Updated {lastLoaded.toLocaleString("vi-VN")}</p>}
          </div>
          <button type="button" className="secondary" onClick={()=>load()} disabled={busy||pendingRequest!==null}>Refresh</button>
        </div>
        <div className="admin-controls">
          <label className="admin-assignee">Nhân sự phụ trách<input value={assignee} onChange={event=>setAssignee(event.target.value)} placeholder="vd. Trang"/></label>
          <label className="admin-assignee">Lọc trạng thái<select value={statusFilter} onChange={event=>setStatusFilter(event.target.value)}><option value="open">Đang mở</option><option value="all">Tất cả</option><option value="requested">Mới nhận</option><option value="reviewing">Đang kiểm tra</option><option value="needs_customer">Chờ khách</option><option value="handed_off">Đã chuyển provider</option><option value="cancelled">Đã hủy</option></select></label>
        </div>
        <div className="offer-grid">
          {visibleBookings.map(item=><article className="offer-card card" key={item.id}>
            <div className="eyebrow">{STATUS_LABELS[item.trang_thai]||item.trang_thai} - {item.loai||"inventory"}</div>
            <h2>{item.offer_id}</h2>
            <p>{item.ghi_chu||"Khách chưa để lại ghi chú."}</p>
            <label className="admin-field">Ghi chú nội bộ<input value={notes[item.id]||""} onChange={event=>setNotes(values=>({...values,[item.id]:event.target.value}))} placeholder="Nội dung cần lưu vào lịch sử"/></label>
            <label className="admin-field">Provider reference<input value={references[item.id]||item.provider_reference||""} onChange={event=>setReferences(values=>({...values,[item.id]:event.target.value}))} placeholder="Mã hồ sơ từ provider"/></label>
            <p className="disclaimer">Tạo lúc {new Date(item.ngay_tao).toLocaleString("vi-VN")} - booking_confirmed=false</p>
            <div className="support-actions">
              {item.trang_thai==="requested"&&<button type="button" className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"reviewing")}>Nhận xử lý</button>}
              {item.trang_thai==="reviewing"&&<><button type="button" className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"needs_customer")}>Cần khách bổ sung</button><button type="button" className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"handed_off")}>Chuyển provider</button></>}
              {item.trang_thai==="needs_customer"&&<button type="button" className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"reviewing")}>Tiếp tục</button>}
              {OPEN_STATUSES.includes(item.trang_thai)&&<button type="button" disabled={pendingRequest!==null} onClick={()=>move(item,"cancelled")}>Hủy</button>}
            </div>
          </article>)}
          {visibleBookings.length===0&&<p className="disclaimer">Không có yêu cầu phù hợp bộ lọc.</p>}
        </div>
      </section>

      <section className="card admin-event-audit">
        <div className="panel-title">Event audit log</div>
        <form className="admin-plan-form" onSubmit={loadEvents}>
          <label>Search session/event/payload<input value={eventQuery} onChange={event=>setEventQuery(event.target.value)} placeholder="session, event, token"/></label>
          <button className="primary" disabled={eventsBusy}>{eventsBusy?"Loading...":"Load events"}</button>
        </form>
        <p className="disclaimer">{eventTotal||data.recent_events.length} events shown. Dashboard fallback shows the latest 20 until you load a filtered audit log.</p>
        <div className="admin-events">
          {(events.length?events:data.recent_events).map((event,index)=><article key={`${event.thoi_gian}-${index}`}>
            <strong>{event.su_kien}</strong><span>{new Date(event.thoi_gian).toLocaleString("vi-VN")}</span>
            <code>{event.ma_phien}</code><small>{JSON.stringify(event.du_lieu).slice(0,180)}</small>
          </article>)}
          {events.length===0&&data.recent_events.length===0&&<p className="disclaimer">Chưa có sự kiện nào.</p>}
        </div>
      </section>
    </>}
  </main>;
}
