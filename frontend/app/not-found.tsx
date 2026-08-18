import Link from "next/link";

export default function NotFound() {
  return (
    <main className="empty-state" style={{ minHeight: "60vh", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "48px 24px" }}>
      <div className="empty-art" aria-hidden="true" />
      <h1 style={{ fontSize: "36px", marginBottom: "12px" }}>404 — Không tìm thấy trang</h1>
      <p className="lead" style={{ textAlign: "center", maxWidth: "520px" }}>
        Trang bạn đang tìm kiếm không tồn tại hoặc đã được chuyển sang đường dẫn khác.
      </p>
      <div style={{ display: "flex", gap: "12px", marginTop: "16px" }}>
        <Link href="/" className="primary">
          Về trang chủ
        </Link>
        <Link href="/explore" className="secondary">
          Khám phá vé & dịch vụ
        </Link>
      </div>
    </main>
  );
}
