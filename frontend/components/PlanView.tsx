"use client";

import dynamic from "next/dynamic";
import {FormEvent,useEffect,useLayoutEffect,useMemo,useRef,useState} from "react";
import {createPortal} from "react-dom";
import Image from "next/image";

import {useLocale} from "@/components/LocaleProvider";
import {API_URL, publicShareUrl} from "@/lib/api";
import {getSession} from "@/lib/session";
import type {TranslationKey,WorkspaceTranslationKey} from "@/lib/i18n-core";
import type {Comment,Plan,Slot,ThamSo} from "@/lib/types";

function MapLoading(){const {t}=useLocale();return <div className="card map">{t("mapLoading")}</div>}
const MapView=dynamic(()=>import("./MapView"),{ssr:false,loading:()=> <MapLoading/>});
type BusyAction="save"|"copy"|"download"|"swipe"|"refine"|"versions"|"restore"|"comment"|"resolve"|"feedback"|"regenerate";
type Version={phien_ban:number;ly_do?:string;ngay_tao?:string};
type ReplacementCandidate = {
  id: string;
  ten: string;
  loai: string;
  khu_vuc: string;
};
type UiMessage={key:WorkspaceTranslationKey;values?:Record<string,string|number>};
type ChatItem={role:"assistant"|"user";text?:string;key?:WorkspaceTranslationKey};
class ReplacementRequestError extends Error{constructor(readonly key:"replacementNotFound"|"replacementInvalid"){super();}}
const isRecord=(value:unknown):value is Record<string,unknown>=>typeof value==="object"&&value!==null;
const isCoordinate=(value:unknown)=>isRecord(value)&&typeof value.lat==="number"&&Number.isFinite(value.lat)&&value.lat>=-90&&value.lat<=90&&typeof value.lng==="number"&&Number.isFinite(value.lng)&&value.lng>=-180&&value.lng<=180;
const isSlot=(value:unknown)=>isRecord(value)&&typeof value.bat_dau==="string"&&typeof value.ket_thuc==="string"&&typeof value.dia_diem_id==="string"&&Boolean(value.dia_diem_id)&&typeof value.ten_dia_diem==="string"&&typeof value.mo_ta==="string"&&typeof value.chi_phi==="number"&&Number.isFinite(value.chi_phi)&&typeof value.ghi_chu==="string"&&isCoordinate(value.toa_do);
const isDay=(value:unknown)=>isRecord(value)&&typeof value.thu_tu==="number"&&Number.isInteger(value.thu_tu)&&typeof value.nhan_de==="string"&&Array.isArray(value.khoang_gio)&&value.khoang_gio.length<=100&&value.khoang_gio.every(isSlot);
const isPlan=(value:unknown):value is Plan=>isRecord(value)&&typeof value.tieu_de==="string"&&typeof value.tom_tat==="string"&&typeof value.chi_phi_moi_nguoi==="number"&&Number.isFinite(value.chi_phi_moi_nguoi)&&Array.isArray(value.ngay)&&value.ngay.length<=31&&value.ngay.every(isDay)&&isRecord(value.thoi_tiet)&&typeof value.thoi_tiet.tinh_trang==="string"&&typeof value.thoi_tiet.ghi_chu==="string";
const isComment=(value:unknown):value is Comment=>isRecord(value)&&typeof value.id==="string"&&typeof value.ten_hien_thi==="string"&&typeof value.noi_dung==="string"&&typeof value.da_giai_quyet==="boolean"&&typeof value.ngay_tao==="string";
const isVersion=(value:unknown):value is Version=>isRecord(value)&&typeof value.phien_ban==="number"&&Number.isInteger(value.phien_ban)&&value.phien_ban>0&&(value.ly_do===undefined||typeof value.ly_do==="string")&&(value.ngay_tao===undefined||typeof value.ngay_tao==="string");
const isReplacementCandidate = (
  value: unknown,
): value is ReplacementCandidate =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.ten === "string" &&
  typeof value.loai === "string" &&
  typeof value.khu_vuc === "string";
const parseReplyKey=(value:unknown):WorkspaceTranslationKey|undefined=>value==="swipeSuccess"||value==="assistantWelcome"||value==="refineApplied"?value:undefined;
const isThamSo=(value:unknown):value is ThamSo=>isRecord(value)&&typeof value.ngan_sach==="number"&&Number.isFinite(value.ngan_sach)&&typeof value.so_nguoi==="number"&&Number.isInteger(value.so_nguoi)&&typeof value.thoi_luong==="string";
const toChatItems=(value:unknown):ChatItem[]=>Array.isArray(value)&&value.length>0&&value.every(item=>isRecord(item)&&(item.vai_tro==="user"||item.vai_tro==="assistant")&&typeof item.noi_dung==="string")?value.map(item=>({role:item.vai_tro==="user"?"user":"assistant",text:item.noi_dung})):[];
const isPastUtcDate=(value:unknown)=>{if(typeof value!=="string"||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;const parsed=new Date(`${value}T00:00:00Z`);return !Number.isNaN(parsed.getTime())&&parsed.toISOString().slice(0,10)===value&&value<new Date().toISOString().slice(0,10)};
const safeImageUrl=(value:unknown)=>{if(typeof value!=="string"||!value.trim())return null;try{const parsed=new URL(value,typeof window==="undefined"?"http://localhost":window.location.origin);return parsed.protocol==="http:"||parsed.protocol==="https:"?value:null}catch{return null}};
async function safeJson(response:Response):Promise<unknown>{try{return await response.json()}catch{return null}}
function authHeader():Record<string,string>{try{const auth=localStorage.getItem("auth_token");return auth?{Authorization:`Bearer ${auth}`}:{}}catch{return {}}}
function preferredUnit():"metric"|"imperial"{try{const value=JSON.parse(localStorage.getItem("travel_preferences")||"null");return value?.don_vi==="imperial"?"imperial":"metric"}catch{return "metric"}}
function legacyCopy(value:string):boolean{
  try{
    const textarea=document.createElement("textarea");
    textarea.value=value;
    textarea.setAttribute("readonly","true");
    textarea.style.position="fixed";
    textarea.style.opacity="0";
    textarea.style.top="0";
    textarea.style.left="0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.setSelectionRange(0,textarea.value.length);
    textarea.select();
    const copied=document.execCommand("copy");
    textarea.remove();
    return copied;
  }catch{return false}
}
async function copyShareLink(value:string):Promise<boolean>{
  if(typeof navigator==="undefined")return false;
  if(navigator.clipboard&&window.isSecureContext){
    try{await navigator.clipboard.writeText(value);return true}catch{return false}
  }
  return legacyCopy(value);
}
async function shareViaApi(value:string,title:string,text:string):Promise<"shared"|"cancelled"|"unsupported">{
  if(typeof navigator==="undefined"||!navigator.share)return "unsupported";
  try{
    const shareData={title,text,url:value};
    if(navigator.canShare&&!navigator.canShare(shareData))return "unsupported";
    await navigator.share(shareData);
    return "shared";
  }catch(error){
    if(error instanceof DOMException&&error.name==="AbortError")return "cancelled";
    return "unsupported";
  }
}
const durationKeys:Record<string,TranslationKey>={vai_gio:"fewHours",nua_ngay:"halfDay",ca_ngay:"fullDay",nhieu_ngay:"multiDay"};
const errorMessageKeys=new Set<WorkspaceTranslationKey>(["copyFailed","offlineSaveFailed","actionFailed","refineFailed","versionsFailed","commentsFailed","regenerateFailed","replacementNotFound","replacementInvalid"]);

export default function PlanView({initial,token,version,constraints:initialConstraints}:{initial:Plan;token:string;version:number;constraints?:ThamSo}){
  const {locale,t}=useLocale();
  const [plan,setPlan]=useState(initial),[ver,setVer]=useState(version),[message,setMessage]=useState<UiMessage|null>(null);
  const [selectedId,setSelectedId]=useState(initial.ngay[0]?.khoang_gio[0]?.dia_diem_id),[activeDay,setActiveDay]=useState(0),[chat,setChat]=useState("");
  const [versions,setVersions]=useState<Version[]>([]),[showVersions,setShowVersions]=useState(false),[comments,setComments]=useState<Comment[]>([]),[showComments,setShowComments]=useState(false);
  const [commentName,setCommentName]=useState(t("companion")),[commentText,setCommentText]=useState(""),[showFeedback,setShowFeedback]=useState(false),[feedbackScore,setFeedbackScore]=useState(5),[feedbackText,setFeedbackText]=useState("");
  const [conversation,setConversation]=useState<ChatItem[]>(()=>toChatItems(initial.hoi_thoai).length>0?toChatItems(initial.hoi_thoai):[{role:"assistant",key:"assistantWelcome"}]),[busy,setBusy]=useState<BusyAction|null>(null);
  const [constraints,setConstraints]=useState<ThamSo|null>(initialConstraints??null);
  const [unit,setUnit]=useState<"metric"|"imperial">("metric");
  const [brokenImages,setBrokenImages]=useState<Set<string>>(new Set());
  const [changeFor, setChangeFor] = useState<string | null>(null),
    [deleteFor, setDeleteFor] = useState<string | null>(null),
    [deletePosition,setDeletePosition]=useState({left:16,top:16}),
    [customSearch, setCustomSearch] = useState(false),
    [searchText, setSearchText] = useState(""),
    [suggestions, setSuggestions] = useState<ReplacementCandidate[]>([]),
    [searchStatus,setSearchStatus]=useState<"idle"|"loading"|"empty"|"error">("idle");
  const busyRef=useRef<BusyAction|null>(null),mounted=useRef(true),previousCompanion=useRef(commentName),controllers=useRef(new Set<AbortController>()),currentToken=useRef(token),verRef=useRef(version),searchGeneration=useRef(0),searchTimer=useRef<ReturnType<typeof setTimeout>|null>(null),changeTrigger=useRef<HTMLButtonElement|null>(null),deleteTrigger=useRef<HTMLButtonElement|null>(null);
  const slots=useMemo(()=>plan.ngay[activeDay]?.khoang_gio??[],[plan,activeDay]);
  const money=useMemo(()=>new Intl.NumberFormat(locale,{style:"currency",currency:"VND",maximumFractionDigits:0}),[locale]);
  const date=useMemo(()=>new Intl.DateTimeFormat(locale,{dateStyle:"medium",timeStyle:"short"}),[locale]);
  const start=(action:BusyAction)=>{if(busyRef.current)return false;busyRef.current=action;setBusy(action);setMessage(null);return true};
  const active=()=>mounted.current&&currentToken.current===token;
  const finish=()=>{if(!active())return;busyRef.current=null;setBusy(null)};
  const closeDelete=()=>{setDeleteFor(null);requestAnimationFrame(()=>deleteTrigger.current?.focus())};
  const closeChange=()=>{const trigger=changeTrigger.current;if(searchTimer.current)clearTimeout(searchTimer.current);setChangeFor(null);setCustomSearch(false);setSearchText("");setSuggestions([]);setSearchStatus("idle");searchGeneration.current+=1;requestAnimationFrame(()=>trigger?.focus())};
  const fail=(key:"actionFailed"|"refineFailed"|"versionsFailed"|"commentsFailed"|"regenerateFailed")=>active()&&setMessage({key});
  const request=async(input:RequestInfo|URL,init:RequestInit={},timeoutMs=30000)=>{const requestToken=token,controller=new AbortController();controllers.current.add(controller);const timeout=setTimeout(()=>controller.abort(),timeoutMs);try{const response=await fetch(input,{...init,signal:controller.signal});if(currentToken.current!==requestToken)throw new DOMException("Stale plan request","AbortError");return response}finally{clearTimeout(timeout);controllers.current.delete(controller)}};

  useEffect(()=>{const activeControllers=controllers.current;mounted.current=true;return()=>{mounted.current=false;if(searchTimer.current)clearTimeout(searchTimer.current);activeControllers.forEach(controller=>controller.abort());activeControllers.clear()}},[]);
  useLayoutEffect(()=>{currentToken.current=token},[token]);
  useEffect(()=>()=>{controllers.current.forEach(controller=>controller.abort());controllers.current.clear()},[token]);
  useEffect(()=>{busyRef.current=null;setBusy(null);setPlan(initial);setVer(version);verRef.current=version;setSelectedId(initial.ngay[0]?.khoang_gio[0]?.dia_diem_id);setActiveDay(0);setVersions([]);setShowVersions(false);setComments([]);setShowComments(false);setShowFeedback(false);setChangeFor(null);setDeleteFor(null);setCustomSearch(false);setSearchText("");setSuggestions([]);setMessage(null);setConstraints(initialConstraints??null);setConversation(toChatItems(initial.hoi_thoai).length>0?toChatItems(initial.hoi_thoai):[{role:"assistant",key:"assistantWelcome"}])},[token,initial,version,initialConstraints]);
  useEffect(()=>{const next=t("companion");setCommentName(current=>current===previousCompanion.current?next:current);previousCompanion.current=next},[locale,t]);
  useEffect(()=>{const sync=()=>setUnit(preferredUnit());sync();window.addEventListener("travel-preferences-changed",sync);return()=>window.removeEventListener("travel-preferences-changed",sync)},[]);
  useEffect(()=>{setActiveDay(day=>Math.min(day,Math.max(0,plan.ngay.length-1)))},[plan.ngay.length]);
  useEffect(()=>{const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),30000);let active=true;(async()=>{try{const response=await fetch(`${API_URL}/api/plans/${token}/comments`,{signal:controller.signal,headers:{"X-Session-Id":getSession()}});const data=await safeJson(response);if(!response.ok||!isRecord(data)||!Array.isArray(data.ds_binh_luan)||!data.ds_binh_luan.every(isComment))throw new Error();if(active&&mounted.current)setComments(data.ds_binh_luan)}catch(error){if(active&&mounted.current)setMessage(current=>current??{key:"commentsFailed"})}})();return()=>{active=false;clearTimeout(timeout);controller.abort()}},[token]);
  useEffect(()=>{if(!message)return;const timer=setTimeout(()=>setMessage(null),5000);return()=>clearTimeout(timer)},[message]);
  useEffect(()=>{if(!changeFor)return;document.querySelector<HTMLButtonElement>(`#change-${CSS.escape(changeFor)} .change-choice`)?.focus();const dismiss=(event:KeyboardEvent|MouseEvent)=>{if(event instanceof KeyboardEvent&&event.key!=="Escape")return;const menu=document.getElementById(`change-${changeFor}`);if(event instanceof MouseEvent&&(menu?.contains(event.target as Node)||changeTrigger.current?.contains(event.target as Node)))return;closeChange()};document.addEventListener("keydown",dismiss);document.addEventListener("mousedown",dismiss);return()=>{document.removeEventListener("keydown",dismiss);document.removeEventListener("mousedown",dismiss)}},[changeFor]);
  useLayoutEffect(()=>{if(!deleteFor)return;const position=()=>{const trigger=deleteTrigger.current,menu=document.getElementById(`delete-${deleteFor}`);if(!trigger||!menu)return;const rect=trigger.getBoundingClientRect(),menuRect=menu.getBoundingClientRect(),gap=8;let left=Math.min(window.innerWidth-menuRect.width-12,Math.max(12,rect.right-menuRect.width));let top=rect.bottom+gap;if(top+menuRect.height>window.innerHeight-12)top=Math.max(12,rect.top-menuRect.height-gap);setDeletePosition({left,top})};position();window.addEventListener("resize",position);window.addEventListener("scroll",position,true);return()=>{window.removeEventListener("resize",position);window.removeEventListener("scroll",position,true)}},[deleteFor]);
  useEffect(()=>{if(!deleteFor)return;const dismiss=(event:KeyboardEvent|MouseEvent)=>{if(event instanceof KeyboardEvent&&event.key!=="Escape")return;const menu=document.getElementById(`delete-${deleteFor}`);if(event instanceof MouseEvent&&(menu?.contains(event.target as Node)||deleteTrigger.current?.contains(event.target as Node)))return;closeDelete()};document.addEventListener("keydown",dismiss);document.addEventListener("mousedown",dismiss);return()=>{document.removeEventListener("keydown",dismiss);document.removeEventListener("mousedown",dismiss)}},[deleteFor]);

  async function copy(){if(!start("copy"))return;const url=publicShareUrl(token);try{const result=await shareViaApi(url,plan.tieu_de,plan.tom_tat);if(result==="shared"){setMessage({key:"shared"})}else if(result==="cancelled"){setMessage(null)}else{setMessage({key:await copyShareLink(url)?"copied":"copyFailed"})}}catch{setMessage({key:"copyFailed"})}finally{finish()}}
  function saveOffline(){if(!start("save"))return;try{localStorage.setItem(`offline-plan:${token}`,JSON.stringify({plan,version:ver,savedAt:new Date().toISOString()}));setMessage({key:"planSaved"})}catch{setMessage({key:"offlineSaveFailed"})}finally{finish()}}
  function downloadJson(){if(!start("download"))return;let url:string|null=null,anchor:HTMLAnchorElement|null=null;try{const blob=new Blob([JSON.stringify(plan,null,2)],{type:"application/json"});url=URL.createObjectURL(blob);anchor=document.createElement("a");anchor.href=url;anchor.download=`itinerary-${token}.json`;anchor.style.display="none";document.body.appendChild(anchor);anchor.click()}catch{fail("actionFailed")}finally{anchor?.remove();if(url)URL.revokeObjectURL(url);finish()}}
  async function swipe(id: string, replacementId?:string, replacementText?:string){if(!start("swipe"))return;const session=getSession();try{const response=await request(`${API_URL}/api/plans/${token}/swipe`,{method:"PATCH",headers:{"Content-Type":"application/json","X-Session-Id":session,...authHeader(),},body:JSON.stringify({diem_bi_loai:id,dia_diem_thay_the:replacementId,ten_dia_diem_thay_the:replacementText?.trim()||undefined,phien_ban:verRef.current,ma_phien:session,}),}),data=await safeJson(response);if(response.status===404)throw new ReplacementRequestError("replacementNotFound");if(response.status===422||response.status===503)throw new ReplacementRequestError("replacementInvalid");if(!response.ok||!isRecord(data)||!isPlan(data.ke_hoach_moi)||typeof data.phien_ban!=="number"||!Number.isInteger(data.phien_ban)||data.phien_ban<=verRef.current)throw new Error();if(!active())return null;const oldIds=new Set(plan.ngay.flatMap((day)=>day.khoang_gio).map((slot)=>slot.dia_diem_id),);const replacement=data.ke_hoach_moi.ngay.flatMap((day)=>day.khoang_gio).find((slot)=>!oldIds.has(slot.dia_diem_id));const nextConversation=toChatItems(data.hoi_thoai);setPlan(data.ke_hoach_moi);setVer(data.phien_ban);verRef.current=data.phien_ban;setSelectedId(replacement?.dia_diem_id??data.ke_hoach_moi.ngay[0]?.khoang_gio[0]?.dia_diem_id,
      );
      setChangeFor(null);
      setCustomSearch(false);
      setSuggestions([]);changeTrigger.current?.focus();setConversation(nextConversation.length>0?nextConversation:(items)=>[...items,{role:"assistant",key:"swipeSuccess"}],);setMessage({key:"swipeSuccess"});return replacement?.ten_dia_diem??null;}catch(error){setMessage({key:error instanceof ReplacementRequestError?error.key:"actionFailed"});return null;}finally{finish();
    }
  }
  async function searchReplacements(id: string, query = searchText) {
    const generation=++searchGeneration.current;
    setSearchStatus("loading");
    const session = getSession();
    try {
      const response = await request(
          `${API_URL}/api/plans/${token}/replacement-candidates?diem_bi_loai=${encodeURIComponent(id)}&q=${encodeURIComponent(query.trim())}`,
          { headers: { "X-Session-Id": session, ...authHeader() } },
        ),
        data = await safeJson(response);
      if (
        !response.ok ||
        !isRecord(data) ||
        !Array.isArray(data.goi_y) ||
        !data.goi_y.every(isReplacementCandidate)
      )
        throw new Error();
      if (active()&&generation===searchGeneration.current&&changeFor===id){setSuggestions(data.goi_y);setSearchStatus(data.goi_y.length?"idle":"empty")}
    } catch {
      if(generation===searchGeneration.current){setSuggestions([]);setSearchStatus("error")}
    }
  }
  function queueReplacementSearch(id:string,value:string){setSearchText(value);if(searchTimer.current)clearTimeout(searchTimer.current);if(value.trim().length<2){searchGeneration.current+=1;setSuggestions([]);setSearchStatus("idle");return}searchTimer.current=setTimeout(()=>{void searchReplacements(id,value)},300)}
  async function deleteSlot(slot: Slot) {
    if (!start("swipe")) return;
    const session = getSession();
    try {
      const response = await request(`${API_URL}/api/plans/${token}/slots`, {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
            "X-Session-Id": session,
            ...authHeader(),
          },
          body: JSON.stringify({
            dia_diem_id: slot.dia_diem_id,
            phien_ban: verRef.current,
            ma_phien: session,
          }),
        }),
        data = await safeJson(response);
      if (
        !response.ok ||
        !isRecord(data) ||
        !isPlan(data.ke_hoach_moi) ||
        typeof data.phien_ban !== "number" ||
        !Number.isInteger(data.phien_ban) ||
        data.phien_ban <= verRef.current
      )
        throw new Error();
      if (!active()) return;
      setPlan(data.ke_hoach_moi);
      setVer(data.phien_ban);
      verRef.current = data.phien_ban;
      const remaining = data.ke_hoach_moi.ngay.flatMap((day) => day.khoang_gio);
      setSelectedId((current) =>
        current === slot.dia_diem_id ? remaining[0]?.dia_diem_id : current,
      );
      setDeleteFor(null);
      setChangeFor(null);
      setCustomSearch(false);setSearchText("");setSuggestions([]);setSearchStatus("idle");searchGeneration.current+=1;
      setMessage({ key: "deletePlaceSuccess" });
      requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>(".itinerary-panel .slot-select")?.focus());
    } catch {
      fail("actionFailed");
    } finally {
      finish();}}
  async function applyRefine(text:string){const messageText=text.trim();if(!messageText||!start("refine"))return;setConversation(items=>[...items,{role:"user",text:messageText}]);setChat("");const session=getSession();try{const response=await request(`${API_URL}/api/plans/${token}/refine`,{method:"POST",headers:{"Content-Type":"application/json","X-Session-Id":session,...authHeader()},body:JSON.stringify({message:messageText,phien_ban:verRef.current,ma_phien:session,dia_diem_dang_chon:selectedId})},90000),data=await safeJson(response),replyKey=isRecord(data)?parseReplyKey(data.tra_loi_key):undefined,replyText=isRecord(data)&&typeof data.tra_loi==="string"?data.tra_loi.trim():"";if(!response.ok||!isRecord(data)||!isPlan(data.ke_hoach)||typeof data.phien_ban!=="number"||!Number.isInteger(data.phien_ban)||data.phien_ban<=0||!(replyKey||replyText))throw new Error();if(!active())return;const nextConversation=toChatItems(data.hoi_thoai);setPlan(data.ke_hoach);setVer(data.phien_ban);verRef.current=data.phien_ban;setSelectedId(data.ke_hoach.ngay[0]?.khoang_gio[0]?.dia_diem_id);setConstraints(isThamSo(data.tham_so)?data.tham_so:constraints);setConversation(nextConversation.length>0?nextConversation:items=>[...items,replyText?{role:"assistant",text:replyText}:replyKey?{role:"assistant",key:replyKey}:{role:"assistant",key:"refineFailed"}])}catch{if(active())setConversation(items=>[...items,{role:"assistant",key:"refineFailed"}])}finally{finish()}}
  async function sendChat(event:FormEvent){event.preventDefault();await applyRefine(chat)}
  async function loadVersions(){if(showVersions){setShowVersions(false);return}if(!start("versions"))return;try{const session=getSession(),response=await request(`${API_URL}/api/plans/${token}/versions`,{headers:{"X-Session-Id":session,...authHeader()}}),data=await safeJson(response);if(!response.ok||!isRecord(data)||!Array.isArray(data.ds_phien_ban)||!data.ds_phien_ban.every(isVersion)||new Set(data.ds_phien_ban.map(item=>item.phien_ban)).size!==data.ds_phien_ban.length)throw new Error();if(!active())return;setVersions(data.ds_phien_ban);setShowVersions(true)}catch{fail("versionsFailed")}finally{finish()}}
  async function restore(target:number){if(!start("restore"))return;const session=getSession();try{const response=await request(`${API_URL}/api/plans/${token}/versions/${target}/restore`,{method:"POST",headers:{"Content-Type":"application/json","X-Session-Id":session,...authHeader()},body:JSON.stringify({phien_ban_hien_tai:verRef.current,ma_phien:session})}),data=await safeJson(response);if(!response.ok||!isRecord(data)||!isPlan(data.ke_hoach)||typeof data.phien_ban!=="number"||!Number.isInteger(data.phien_ban)||data.phien_ban<=verRef.current)throw new Error();if(!active())return;setPlan(data.ke_hoach);setVer(data.phien_ban);verRef.current=data.phien_ban;setSelectedId(data.ke_hoach.ngay[0]?.khoang_gio[0]?.dia_diem_id);setShowVersions(false);setChangeFor(null);setCustomSearch(false);setSearchText("");setSuggestions([]);searchGeneration.current+=1;setMessage({key:"restoreSuccess",values:{target,version:data.phien_ban}})}catch{fail("actionFailed")}finally{finish()}}
  async function addComment(event:FormEvent){event.preventDefault();if(!commentText.trim()||!commentName.trim()||!start("comment"))return;const session=getSession();try{const response=await request(`${API_URL}/api/plans/${token}/comments`,{method:"POST",headers:{"Content-Type":"application/json",...authHeader()},body:JSON.stringify({noi_dung:commentText.trim(),ten_hien_thi:commentName.trim(),ma_phien:session})}),data=await safeJson(response);if(response.status===401){try{localStorage.removeItem("auth_token")}catch{}}if(!response.ok||!isRecord(data)||!isComment(data.binh_luan))throw new Error();if(!active())return;const savedComment=data.binh_luan;setComments(items=>[...items,savedComment]);setCommentText("");setMessage({key:"commentAdded"})}catch{fail("commentsFailed")}finally{finish()}}
  async function resolveComment(comment:Comment){if(!start("resolve"))return;const session=getSession();try{const response=await request(`${API_URL}/api/plans/${token}/comments/${encodeURIComponent(comment.id)}`,{method:"PATCH",headers:{"Content-Type":"application/json",...authHeader()},body:JSON.stringify({da_giai_quyet:!comment.da_giai_quyet,ma_phien:session})}),data=await safeJson(response);if(response.status===401){try{localStorage.removeItem("auth_token")}catch{}}if(!response.ok||!isRecord(data)||!isComment(data.binh_luan))throw new Error();if(!active())return;const updatedComment=data.binh_luan;setComments(items=>items.map(item=>item.id===comment.id?updatedComment:item))}catch{fail("commentsFailed")}finally{finish()}}
  async function submitFeedback(event:FormEvent){event.preventDefault();if(!start("feedback"))return;const session=getSession();try{const response=await request(`${API_URL}/api/plans/${token}/feedback`,{method:"POST",headers:{"Content-Type":"application/json",...authHeader()},body:JSON.stringify({diem:feedbackScore,noi_dung:feedbackText.trim(),ma_phien:session})});if(response.status===401){try{localStorage.removeItem("auth_token")}catch{}}if(!response.ok)throw new Error();if(!active())return;setShowFeedback(false);setMessage({key:"feedbackThanks"})}catch{fail("actionFailed")}finally{finish()}}
  async function regenerate(){if(!start("regenerate"))return;const session=getSession(),nonceKey=`regenerate-nonce:${token}`;let nonce="";try{nonce=sessionStorage.getItem(nonceKey)||crypto.randomUUID();sessionStorage.setItem(nonceKey,nonce)}catch{nonce=crypto.randomUUID()}try{const response=await request(`${API_URL}/api/plans/${token}/regenerate`,{method:"POST",headers:{"Content-Type":"application/json","X-Session-Id":session,...authHeader()},body:JSON.stringify({ma_phien:session,nonce})},90000),data=await safeJson(response);if(!response.ok||!isRecord(data)||!isPlan(data.ke_hoach)||typeof data.token!=="string"||!/^[A-Za-z0-9_-]+$/.test(data.token)||data.token!==token||typeof data.phien_ban!=="number"||!Number.isInteger(data.phien_ban)||data.phien_ban<=verRef.current)throw new Error();if(!active())return;try{sessionStorage.removeItem(nonceKey)}catch{}setPlan(data.ke_hoach);setVer(data.phien_ban);verRef.current=data.phien_ban;setActiveDay(0);setSelectedId(data.ke_hoach.ngay[0]?.khoang_gio[0]?.dia_diem_id);setConversation(items=>[...items,{role:"assistant",key:"regenerateSuccess"}]);setMessage({key:"regenerateSuccess"})}catch{fail("regenerateFailed")}finally{finish()}}
  const disabled=busy!==null;
  const summaryImage=slots.find(slot=>{const url=safeImageUrl(slot.anh);return Boolean(url&&!brokenImages.has(url))});
  const selectSlot=(id:string)=>setSelectedId(id);
  const returnToChat=()=>window.location.assign("/");
  const hideImage=(url:string)=>setBrokenImages(current=>{if(current.has(url))return current;const next=new Set(current);next.add(url);return next});
  const slotPhoto=(slot:Slot)=>{const url=safeImageUrl(slot.anh);return url&&!brokenImages.has(url)?<div className="slot-photo"><Image src={url} alt="" fill sizes="(max-width:760px) 100vw, 33vw" loading="lazy" referrerPolicy="no-referrer" unoptimized onError={()=>hideImage(url)}/></div>:null};

  return <main className="workspace-page">
    <div className="result-topbar">
      <button type="button" className="result-back-to-chat" onClick={returnToChat}>
        <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/><path d="M9 12h10"/></svg>
        {t("backToChat")}
      </button>
      <span className="result-ready-badge"><span aria-hidden="true">✦</span> {t("aiFinished")}</span>
    </div>
    {message&&<div className={`action-toast ${errorMessageKeys.has(message.key)?"error":"success"}`} role="status" aria-live="polite" aria-atomic="true">{t(message.key,message.values)}</div>}{busy&&<div className="status busy" role="status"><span className="spinner" aria-hidden="true"/>{t("busy")}</div>}
    {showVersions&&<section className="version-drawer card"><div className="panel-title">{t("versionHistory")}</div>{versions.map(entry=>{const parsedDate=entry.ngay_tao?new Date(entry.ngay_tao):null;const dateLabel=parsedDate&&!Number.isNaN(parsedDate.getTime())?` · ${date.format(parsedDate)}`:"";return <div className="version-row" key={entry.phien_ban}><div><strong>{t("version",{version:entry.phien_ban})}</strong><small>{entry.ly_do||t("scheduleUpdate")}{dateLabel}</small></div>{entry.phien_ban!==ver&&<button className="secondary" disabled={disabled} onClick={()=>restore(entry.phien_ban)}>{t("restore")}</button>}</div>})}</section>}
    {showComments&&<section className="comment-drawer card"><div className="panel-title">{t("groupDiscussion")}</div><div className="comment-list">{comments.length===0&&<p className="disclaimer">{t("noComments")}</p>}{comments.map(comment=><article className={comment.da_giai_quyet?"comment resolved":"comment"} key={comment.id}><div><strong>{comment.ten_hien_thi}</strong><p>{comment.noi_dung}</p></div><button className="secondary" disabled={disabled} onClick={()=>resolveComment(comment)}>{comment.da_giai_quyet?t("reopen"):t("resolved")}</button></article>)}</div><form className="comment-form" onSubmit={addComment}><input value={commentName} onChange={event=>setCommentName(event.target.value)} maxLength={80} aria-label={t("displayName")} required/><input value={commentText} onChange={event=>setCommentText(event.target.value)} maxLength={1000} placeholder={t("commentPlaceholder")} aria-label={t("commentPlaceholder")} required/><button className="primary" disabled={disabled}>{t("sendComment")}</button></form></section>}
    {showFeedback&&<form className="feedback-card card" onSubmit={submitFeedback}><div className="panel-title">{t("tripReview")}</div><label>{t("rating")}<select value={feedbackScore} disabled={disabled} onChange={event=>setFeedbackScore(Number(event.target.value))}>{[5,4,3,2,1].map(score=><option value={score} key={score}>{score}/5</option>)}</select></label><textarea value={feedbackText} disabled={disabled} onChange={event=>setFeedbackText(event.target.value)} maxLength={2000} placeholder={t("feedbackPlaceholder")} aria-label={t("feedbackPlaceholder")}/><button className="primary" disabled={disabled}>{t("sendFeedback")}</button></form>}
    <div className="workspace"><aside className="chat-panel card" aria-label={t("tripAssistant")}><div className="panel-title"><span className="assistant-dot"/>{t("tripAssistant")}</div><div className="messages" aria-live="polite">{conversation.map((item,index)=><div key={index} className={`bubble ${item.role}`}>{item.key?t(item.key):item.text}</div>)}</div><form className="chat-box" onSubmit={sendChat}><input value={chat} disabled={disabled} onChange={event=>setChat(event.target.value)} placeholder={t("chatPlaceholder")} aria-label={t("chatPlaceholder")}/><button disabled={disabled} aria-label={t("send")}>↑</button></form></aside>
      <section className="itinerary-panel card" aria-labelledby="itinerary-card-title"><div className="itinerary-card-hero">{summaryImage&&safeImageUrl(summaryImage.anh)&&<Image src={safeImageUrl(summaryImage.anh)!} alt={summaryImage.ten_dia_diem} fill priority sizes="(max-width:760px) 100vw, 50vw" referrerPolicy="no-referrer" unoptimized onError={()=>hideImage(safeImageUrl(summaryImage.anh)!)}/>}</div><div className="itinerary-card-body"><h2 id="itinerary-card-title">{plan.tieu_de}</h2><div className="itinerary-summary-facts"><span>💵 {money.format(plan.chi_phi_moi_nguoi)}</span><span>◷ {t(durationKeys[constraints?.thoi_luong??plan.thoi_luong]??constraints?.thoi_luong??plan.thoi_luong)}</span><span>☀ {plan.thoi_tiet.tinh_trang}{plan.thoi_tiet.nhiet_do_max!==undefined?` · ${unit==="imperial"?Math.round(plan.thoi_tiet.nhiet_do_max*9/5+32):plan.thoi_tiet.nhiet_do_max}°${unit==="imperial"?"F":"C"}`:""}</span></div><div className="day-tabs" aria-label={t("itinerary")}>{plan.ngay.map((day,index)=><button className={index===activeDay?"active":""} onClick={()=>setActiveDay(index)} key={`${day.thu_tu}-${index}`}>{day.nhan_de}</button>)}</div><div className="timeline">{slots.length===0&&<p className="itinerary-empty">{t("noStops")}</p>}{slots.map((slot,index)=>(<article className={`slot ${selectedId === slot.dia_diem_id ? "selected" : ""}`} key={`${activeDay}-${index}-${slot.dia_diem_id}`}><button type="button" className="slot-select" aria-pressed={selectedId===slot.dia_diem_id} aria-label={slot.ten_dia_diem} onClick={()=>selectSlot(slot.dia_diem_id)}/>{slotPhoto(slot)}<div className="stop-index">{index+1}</div><strong>{slot.bat_dau}<br/><span>{slot.ket_thuc}</span></strong><div>{slot.nhan_bua&&(<span className="meal-badge">{slot.nhan_bua}</span>)}<h3>{slot.ten_dia_diem}</h3><p>{slot.mo_ta}</p><div className="slot-meta"><small>{money.format(slot.chi_phi)} · {slot.ghi_chu}</small>{slot.nguon_url&&<> <a className="source" href={slot.nguon_url} target="_blank" rel="noreferrer">{t("source",{source:slot.nguon||slot.nguon_url})}</a></>}</div></div><div className="slot-actions">
                    <button className="secondary change-place"
                      ref={changeFor===slot.dia_diem_id?changeTrigger:undefined}
                      type="button" disabled={disabled} aria-expanded={changeFor === slot.dia_diem_id}
                      aria-controls={`change-${slot.dia_diem_id}`}
                      onClick={() => {
                        setDeleteFor(null);
                        setChangeFor((current) =>
                          current === slot.dia_diem_id
                            ? null
                            : slot.dia_diem_id,
                        );
                        setCustomSearch(false);
                        setSuggestions([]);
                        setSearchStatus("idle");searchGeneration.current+=1;
                      }}
                    >
                      <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7h3c4 0 6 10 10 10h5"/><path d="m18 14 3 3-3 3"/><path d="M3 17h3c4 0 6-10 10-10h5"/><path d="m18 4 3 3-3 3"/></svg>
                      {t("changePlace")}
                    </button>
                    <button
                      className="icon-action delete-place"
                      type="button"
                      disabled={disabled}
                      title={t("deletePlace")}
                      aria-label={t("deletePlaceLabel", {
                        place: slot.ten_dia_diem,
                      })}
                      aria-expanded={deleteFor===slot.dia_diem_id}
                      aria-controls={`delete-${slot.dia_diem_id}`}
                      onClick={(event) => {deleteTrigger.current=event.currentTarget;setChangeFor(null);setDeleteFor(current=>current===slot.dia_diem_id?null:slot.dia_diem_id)}}
                    >
                        <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v5M14 11v5" />
                        </svg>
                    </button>
                    {deleteFor===slot.dia_diem_id&&typeof document!=="undefined"&&createPortal(<div className="delete-menu" style={deletePosition} id={`delete-${slot.dia_diem_id}`} role="dialog" aria-modal="true" aria-label={t("deletePlaceLabel",{place:slot.ten_dia_diem})}><p>{t("deletePlaceConfirm",{place:slot.ten_dia_diem})}</p><div><button type="button" className="secondary" autoFocus onClick={closeDelete}>{t("deletePlaceCancel")}</button><button type="button" className="danger" onClick={()=>void deleteSlot(slot)}>{t("deletePlace")}</button></div></div>,document.body)}
                  </div>
                  {changeFor === slot.dia_diem_id && typeof document!=="undefined" && createPortal(
                    <div
                      className="change-menu"
                      id={`change-${slot.dia_diem_id}`}
                      role="dialog"
                      aria-label={t("changePlaceOptions")}
                    >
                      <button type="button" className="change-menu-close" aria-label={t("changePlaceClose")} title={t("changePlaceClose")} onClick={closeChange}><svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
                      <button
                        type="button"
                        className="change-choice"onClick={()=>{void swipe(slot.dia_diem_id);}}>
                        {t("aiReplace")}
                      </button>
                      <button
                        type="button"
                        className="change-choice"
                        onClick={() => {
                          setCustomSearch(true);
                          setSearchText("");setSuggestions([]);setSearchStatus("idle");
                        }}
                      >
                        {t("chooseReplacement")}
                      </button>
                      {customSearch && (
                        <form
                          className="replacement-search"
                          onSubmit={(event) => {
                            event.preventDefault();
                            if(searchText.trim())void swipe(slot.dia_diem_id,undefined,searchText);
                          }}
                        >
                          <label htmlFor={`replacement-${slot.dia_diem_id}`}>
                            {t("replacementSearchLabel")}
                          </label>
                          <div>
                            <input
                              id={`replacement-${slot.dia_diem_id}`}
                              autoFocus
                              value={searchText}
                              role="combobox" aria-autocomplete="list" aria-controls={`suggestions-${slot.dia_diem_id}`} aria-expanded={suggestions.length>0}
                              onChange={(event) =>queueReplacementSearch(slot.dia_diem_id,event.target.value)}
                              placeholder={t("replacementSearchPlaceholder")}/><button className="secondary" type="submit">
                              {t("changePlace")}</button></div>
                          {searchStatus==="loading"&&<p role="status">{t("replacementLoading")}</p>}
                          {searchStatus==="empty"&&<p role="status">{t("replacementEmpty")}</p>}
                          {searchStatus==="error"&&<p role="alert">{t("replacementError")}</p>}
                          <ul id={`suggestions-${slot.dia_diem_id}`} aria-label={t("replacementSuggestions")}>
                            {suggestions.map((candidate) => (
                              <li key={candidate.id}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    void swipe(slot.dia_diem_id, candidate.id);
                                  }}
                                >
                                  <strong>{candidate.ten}</strong>
                                  <small>
                                    {candidate.loai} · {candidate.khu_vuc}
                                  </small>
                                </button>
                              </li>
                            ))}
                          </ul>
                        </form>
                      )}
                    </div>,document.body
                  )}
                </article>))}</div><div className="itinerary-export-actions"><a className="secondary button-link" href={`${API_URL}/api/plans/${token}/itinerary.pdf`}><span aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4"/><path d="M9 13h6M9 17h4"/></svg></span>{t("downloadPdf")}</a><a className="secondary button-link" href={`${API_URL}/api/plans/${token}/calendar.ics`}><span aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 2v4M16 2v4M3 9h18"/><rect x="4" y="5" width="16" height="16" rx="2"/><path d="M12 13v4M10 15h4"/></svg></span>{t("addCalendar")}</a></div><div className="itinerary-summary-actions"><button className="primary" type="button" onClick={saveOffline} disabled={disabled}><span aria-hidden="true">▯</span> {t("savePlan")}</button><button className="secondary" type="button" onClick={copy} disabled={disabled}><span aria-hidden="true">⌯</span> {t("share")}</button></div><button className="itinerary-regenerate secondary" type="button" onClick={regenerate} disabled={disabled}><span aria-hidden="true">↻</span> {t("regenerate")}</button></div></section>
      <section className="map-panel"><MapView slots={slots} selectedId={selectedId} onSelect={setSelectedId}/><div className="map-legend card">{t("mapLegend")}</div></section></div>
    <p className="disclaimer">{t("estimateDisclaimer",{weather:plan.thoi_tiet.ghi_chu})}</p>
  </main>
}
