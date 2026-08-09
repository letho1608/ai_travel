import type { Metadata } from "next";
import { notFound } from "next/navigation";
import PlanView from "@/components/PlanView";
import { API_URL, BASE_URL } from "@/lib/api";
async function load(token:string){const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),8000);try{const r=await fetch(`${API_URL}/api/plans/${token}`,{cache:"no-store",signal:controller.signal});if(!r.ok)throw new Error("Kế hoạch không tồn tại hoặc đã hết hạn");return r.json()}finally{clearTimeout(timeout)}}
export async function generateMetadata({params}:{params:{token:string}}):Promise<Metadata>{try{const d=await load(params.token);const base=BASE_URL??"http://localhost:3000";const title=d.ke_hoach.tieu_de,description=d.ke_hoach.tom_tat;return{metadataBase:new URL(base),title,description,openGraph:{title,description,url:`${base}/plan/${params.token}`,type:"website",images:[{url:`${base}/og.png`,width:1200,height:630,alt:title}]},twitter:{card:"summary_large_image",title,description,images:[`${base}/og.png`]}}}catch{return{title:"Kế hoạch không tồn tại"}}}
export default async function Page({params}:{params:{token:string}}){let d;try{d=await load(params.token)}catch{notFound()}return <PlanView initial={d.ke_hoach} token={params.token} version={d.phien_ban} constraints={d.tham_so}/>}
