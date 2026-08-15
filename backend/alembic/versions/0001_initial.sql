CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS dia_diem (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), ten text NOT NULL, ten_bo_dau text NOT NULL,
  loai text NOT NULL, khu_vuc text, dia_chi text, gia_trung_binh integer,
  tags text[] DEFAULT '{}', phong_cach text[] DEFAULT '{}', gio_mo_cua jsonb,
  toa_do jsonb NOT NULL, mo_ta text, hinh_anh text, hinh_anh_nguon text, nguon text NOT NULL,
  nguon_url text UNIQUE, website text, ma_nguon text UNIQUE, thoi_luong_phut integer NOT NULL DEFAULT 60,
  diem_danh_gia numeric(2,1), so_nhan_xet integer, google_place_id text, google_maps_url text,
  trang_thai text NOT NULL DEFAULT 'active', ngay_tao timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bang_khoang_cach (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), diem_a_id uuid REFERENCES dia_diem(id),
  diem_b_id uuid REFERENCES dia_diem(id), phuong_tien text NOT NULL,
  khoang_cach_met integer NOT NULL, thoi_gian_giay integer NOT NULL, ngay_cap_nhat timestamptz NOT NULL,
  UNIQUE(diem_a_id, diem_b_id, phuong_tien)
);
CREATE TABLE IF NOT EXISTS nguoi_dung (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), nha_cung_cap text NOT NULL,
  email text NOT NULL UNIQUE, ten text, ngay_tao timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS consent (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), nguoi_dung_id uuid REFERENCES nguoi_dung(id),
  ma_phien text, phien_ban_chinh_sach text NOT NULL, dong_y_luc timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ke_hoach (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), ma_chia_se uuid NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
  nguoi_dung_id uuid REFERENCES nguoi_dung(id), ma_phien text NOT NULL, du_lieu jsonb NOT NULL,
  yeu_cau jsonb NOT NULL DEFAULT '{}',
  ngay_di date, ngay_nhac timestamptz, da_gui_nhac boolean NOT NULL DEFAULT false,
  ngay_tao timestamptz NOT NULL DEFAULT now(), ngay_het_han timestamptz, phien_ban integer NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ho_so_so_thich (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), id_nguoi_dung uuid REFERENCES nguoi_dung(id),
  ma_phien text, trong_so_tag jsonb NOT NULL DEFAULT '{}', ngay_cap_nhat timestamptz NOT NULL DEFAULT now(),
  CHECK (id_nguoi_dung IS NOT NULL OR ma_phien IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS nhat_ky (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), ma_phien text NOT NULL, su_kien text NOT NULL,
  du_lieu jsonb, thoi_gian timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chi_phi_ai_ngay (
  ngay date PRIMARY KEY, tong_usd numeric(12,6) NOT NULL DEFAULT 0,
  so_token_vao bigint NOT NULL DEFAULT 0, so_token_ra bigint NOT NULL DEFAULT 0,
  ngay_cap_nhat timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS idempotency_key (
  plan_token uuid NOT NULL, nonce text NOT NULL, result_token uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(plan_token, nonce)
);
CREATE TABLE IF NOT EXISTS lan_goi_ai (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), nha_cung_cap text NOT NULL,
  model text NOT NULL, token_vao bigint NOT NULL, token_ra bigint NOT NULL,
  chi_phi_usd numeric(12,8) NOT NULL, thanh_cong boolean NOT NULL DEFAULT true,
  thoi_gian timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS phien_ban_ke_hoach (
  ke_hoach_id uuid NOT NULL REFERENCES ke_hoach(id) ON DELETE CASCADE,
  phien_ban integer NOT NULL, du_lieu jsonb NOT NULL, yeu_cau jsonb NOT NULL,
  ly_do text, ngay_tao timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(ke_hoach_id,phien_ban)
);
CREATE TABLE IF NOT EXISTS binh_luan (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  ke_hoach_id uuid NOT NULL REFERENCES ke_hoach(id) ON DELETE CASCADE,
  nguoi_dung_id uuid REFERENCES nguoi_dung(id), ma_phien text,
  ten_hien_thi text NOT NULL, noi_dung text NOT NULL,
  da_giai_quyet boolean NOT NULL DEFAULT false,
  ngay_tao timestamptz NOT NULL DEFAULT now(),
  CHECK (nguoi_dung_id IS NOT NULL OR ma_phien IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_binh_luan_ke_hoach_ngay
  ON binh_luan(ke_hoach_id,ngay_tao);
CREATE TABLE IF NOT EXISTS inventory_snapshot (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), ma_phien text NOT NULL,
  loai text NOT NULL, yeu_cau jsonb NOT NULL, ket_qua jsonb NOT NULL,
  nha_cung_cap text NOT NULL, lay_luc timestamptz NOT NULL,
  het_han_luc timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS yeu_cau_ho_tro_dat (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  snapshot_id uuid NOT NULL REFERENCES inventory_snapshot(id),
  ma_phien text NOT NULL, nguoi_dung_id uuid REFERENCES nguoi_dung(id),
  offer_id text NOT NULL, ghi_chu text, trang_thai text NOT NULL DEFAULT 'requested',
  ngay_tao timestamptz NOT NULL DEFAULT now(),
  CHECK (trang_thai IN ('requested','reviewing','needs_customer','handed_off','cancelled'))
);
ALTER TABLE yeu_cau_ho_tro_dat ADD COLUMN IF NOT EXISTS phu_trach text;
ALTER TABLE yeu_cau_ho_tro_dat ADD COLUMN IF NOT EXISTS provider_reference text;
ALTER TABLE yeu_cau_ho_tro_dat ADD COLUMN IF NOT EXISTS ngay_cap_nhat timestamptz NOT NULL DEFAULT now();
CREATE TABLE IF NOT EXISTS lich_su_ho_tro_dat (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  yeu_cau_id uuid NOT NULL REFERENCES yeu_cau_ho_tro_dat(id) ON DELETE CASCADE,
  trang_thai text NOT NULL,
  phu_trach text NOT NULL,
  ghi_chu_noi_bo text,
  provider_reference text,
  ngay_tao timestamptz NOT NULL DEFAULT now(),
  CHECK (trang_thai IN ('reviewing','needs_customer','handed_off','cancelled'))
);
CREATE INDEX IF NOT EXISTS ix_ho_tro_dat_trang_thai_ngay
  ON yeu_cau_ho_tro_dat(trang_thai,ngay_tao);
CREATE TABLE IF NOT EXISTS phan_hoi_chuyen_di (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  ke_hoach_id uuid NOT NULL REFERENCES ke_hoach(id) ON DELETE CASCADE,
  nguoi_dung_id uuid REFERENCES nguoi_dung(id), ma_phien text,
  diem smallint NOT NULL CHECK (diem BETWEEN 1 AND 5),
  noi_dung text, ngay_tao timestamptz NOT NULL DEFAULT now(),
  CHECK (nguoi_dung_id IS NOT NULL OR ma_phien IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS thong_bao (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  ke_hoach_id uuid NOT NULL REFERENCES ke_hoach(id) ON DELETE CASCADE,
  nguoi_dung_id uuid REFERENCES nguoi_dung(id), ma_phien text,
  loai text NOT NULL, noi_dung text NOT NULL,
  da_doc boolean NOT NULL DEFAULT false, ngay_tao timestamptz NOT NULL DEFAULT now(),
  UNIQUE(ke_hoach_id,loai),
  CHECK (nguoi_dung_id IS NOT NULL OR ma_phien IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_thong_bao_chu_so_huu
  ON thong_bao(nguoi_dung_id,ma_phien,da_doc,ngay_tao);
CREATE UNIQUE INDEX IF NOT EXISTS uq_phan_hoi_phien
  ON phan_hoi_chuyen_di(ke_hoach_id,ma_phien) WHERE nguoi_dung_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_phan_hoi_nguoi_dung
  ON phan_hoi_chuyen_di(ke_hoach_id,nguoi_dung_id) WHERE nguoi_dung_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ho_so_phien
  ON ho_so_so_thich(ma_phien) WHERE id_nguoi_dung IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ho_so_nguoi_dung
  ON ho_so_so_thich(id_nguoi_dung) WHERE ma_phien IS NULL;

ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS nguon_url text;
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS website text;
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS hinh_anh_nguon text;
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS ma_nguon text;
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS thoi_luong_phut integer NOT NULL DEFAULT 60;
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS diem_danh_gia numeric(2,1);
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS so_nhan_xet integer;
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS google_place_id text;
ALTER TABLE dia_diem ADD COLUMN IF NOT EXISTS google_maps_url text;
CREATE UNIQUE INDEX IF NOT EXISTS uq_dia_diem_nguon_url
  ON dia_diem(nguon_url) WHERE nguon_url IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_dia_diem_ma_nguon
  ON dia_diem(ma_nguon) WHERE ma_nguon IS NOT NULL;
ALTER TABLE ho_so_so_thich ADD COLUMN IF NOT EXISTS ngon_ngu text NOT NULL DEFAULT 'vi';
ALTER TABLE ho_so_so_thich ADD COLUMN IF NOT EXISTS tien_te text NOT NULL DEFAULT 'VND';
ALTER TABLE ho_so_so_thich ADD COLUMN IF NOT EXISTS don_vi text NOT NULL DEFAULT 'metric';
ALTER TABLE ho_so_so_thich ADD COLUMN IF NOT EXISTS trong_so_log jsonb NOT NULL DEFAULT '[]';
