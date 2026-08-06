import type { Metadata } from "next";
import { notFound } from "next/navigation";
import PlanView from "@/components/PlanView";
import { API_URL } from "@/lib/api";
async function load(token:string){const r=await fetch(`${API_URL}/api/plans/${token}`,{cache:"no-store"});if(!r.ok)throw new Error("Kế hoạch không tồn tại hoặc đã hết hạn");return r.json()}
export async function generateMetadata({params}:{params:{token:string}}):Promise<Metadata>{try{const d=await load(params.token);return{title:d.ke_hoach.tieu_de,description:d.ke_hoach.tom_tat,openGraph:{title:d.ke_hoach.tieu_de,description:d.ke_hoach.tom_tat}}}catch{return{title:"Kế hoạch không tồn tại"}}}
export default async function Page({params}:{params:{token:string}}){let d;try{d=await load(params.token)}catch{notFound()}return <PlanView initial={d.ke_hoach} token={params.token} version={d.phien_ban}/>}
