export type Slot = { bat_dau: string; ket_thuc: string; dia_diem_id: string; ten_dia_diem: string; loai: string; mo_ta: string; chi_phi: number; toa_do: {lat:number; lng:number}; ghi_chu:string; nguon?:string; nguon_url?:string|null; anh?:string|null; anh_nguon?:string|null; bua_an?:string; nhan_bua?:string; thoi_gian_ly_do?:string };
export type HoiThoaiTurn = { vai_tro:"user"|"assistant"; noi_dung:string; thoi_gian:string };
export type TuyenDuong = {type:"LineString"; coordinates:Array<[number,number]>};
export type Plan = { tieu_de:string; tom_tat:string; thoi_luong:string; ngay_di?:string; tong_chi_phi:number; chi_phi_moi_nguoi:number; thoi_tiet:{tinh_trang:string;ghi_chu:string;nhiet_do_min?:number;nhiet_do_max?:number;xac_suat_mua?:number;nguon?:string}; ngay:Array<{thu_tu:number;nhan_de:string;khoang_gio:Slot[];tuyen_duong?:TuyenDuong|null}>; luu_y:string[]; hoi_thoai?:HoiThoaiTurn[]; ngay_cap_nhat?:string };
export type ThamSo = { ngan_sach:number; so_nguoi:number; thoi_luong:string; ngon_ngu?:string; ngay_di?:string|null };
export type Comment = {id:string;ten_hien_thi:string;noi_dung:string;da_giai_quyet:boolean;ngay_tao:string};
