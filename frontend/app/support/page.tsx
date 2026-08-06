"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { API_URL } from "@/lib/api";

type BookingRequest = {
  id:string; offer_id:string; loai?:string; ghi_chu?:string; trang_thai:string;
  phu_trach?:string; provider_reference?:string; ngay_tao:string;
};

const LABELS:Record<string,string> = {
  requested:"Mới nhận", reviewing:"Đang kiểm tra", needs_customer:"Chờ khách hàng",
  handed_off:"Đã chuyển nhà cung cấp", cancelled:"Đã hủy",
};

export default function SupportPage() {
  const [token,setToken] = useState("");
  const [items,setItems] = useState<BookingRequest[]>([]);
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const [pendingRequest,setPendingRequest] = useState<string|null>(null);
  const pendingRef = useRef<string|null>(null);
  useEffect(()=>setToken(sessionStorage.getItem("support_token")||""),[]);

  async function load(event?:FormEvent) {
    event?.preventDefault(); setBusy(true); setError("");
    sessionStorage.setItem("support_token",token);
    try {
      const response=await fetch(`${API_URL}/api/support/booking-requests`,{headers:{"X-Support-Token":token}});
      const data=await response.json();
      if(!response.ok) throw new Error(data.detail||"Không tải được hàng đợi");
      setItems(data.items);
    } catch(reason) { setError(reason instanceof Error?reason.message:"Không tải được hàng đợi"); }
    finally { setBusy(false); }
  }

  async function move(item:BookingRequest,status:string) {
    if(pendingRef.current) return;
    pendingRef.current=item.id; setPendingRequest(item.id); setError("");
    const assignee=prompt("Ten nhan su phu trach",item.phu_trach||"");
    if(!assignee) { pendingRef.current=null; setPendingRequest(null); return; }
    const note=prompt("Ghi chu noi bo (khong gui cho khach hang)","")||null;
    const providerReference=status==="handed_off"?prompt("Ma ho so nha cung cap (neu co)","")||null:null;
    try {
      const response=await fetch(`${API_URL}/api/support/booking-requests/${item.id}`,{
        method:"PATCH",headers:{"Content-Type":"application/json","X-Support-Token":token},
        body:JSON.stringify({trang_thai:status,phu_trach:assignee,ghi_chu_noi_bo:note,provider_reference:providerReference}),
      });
      const data=await response.json();
      if(!response.ok) { setError(data.detail||"Khong cap nhat duoc yeu cau"); return; }
      await load();
    } finally {
      pendingRef.current=null; setPendingRequest(null);
    }
  }
  return <main className="explore-page">
    <div className="eyebrow">Vận hành nội bộ</div><h1>Hàng đợi hỗ trợ đặt dịch vụ</h1>
    <p className="lead">Nhân sự kiểm tra snapshot và chuyển yêu cầu tới nhà cung cấp. Không trạng thái nào ở đây đồng nghĩa giao dịch đã được xác nhận.</p>
    <form className="card inventory-search" onSubmit={load}><label>Support token<input type="password" value={token} onChange={event=>setToken(event.target.value)} autoComplete="current-password" required/></label><button className="primary" disabled={busy||pendingRequest!==null}>{busy?"Đang tải…":"Mở hàng đợi"}</button></form>
    {error&&<p className="error" role="alert">{error}</p>}
    <div className="offer-grid">{items.map(item=><article className="card offer-card" key={item.id}>
      <div className="eyebrow">{LABELS[item.trang_thai]||item.trang_thai} · {item.loai||"inventory"}</div>
      <h2>{item.offer_id}</h2><p>{item.ghi_chu||"Không có ghi chú từ khách hàng."}</p>
      <p>Phụ trách: {item.phu_trach||"Chưa phân công"}</p>{item.provider_reference&&<p>Hồ sơ provider: {item.provider_reference}</p>}
      <p className="disclaimer">Tạo lúc {new Date(item.ngay_tao).toLocaleString("vi-VN")} · Chưa xác nhận đặt chỗ.</p>
      <div className="support-actions">{item.trang_thai==="requested"&&<><button className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"reviewing")}>Nhận xử lý</button><button disabled={pendingRequest!==null} onClick={()=>move(item,"cancelled")}>Hủy</button></>}{item.trang_thai==="reviewing"&&<><button className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"needs_customer")}>Cần khách bổ sung</button><button className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"handed_off")}>Chuyển provider</button><button disabled={pendingRequest!==null} onClick={()=>move(item,"cancelled")}>Hủy</button></>}{item.trang_thai==="needs_customer"&&<><button className="secondary" disabled={pendingRequest!==null} onClick={()=>move(item,"reviewing")}>Tiếp tục xử lý</button><button disabled={pendingRequest!==null} onClick={()=>move(item,"cancelled")}>Hủy</button></>}</div>
    </article>)}</div>
  </main>;
}
