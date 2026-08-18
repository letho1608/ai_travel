"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ExploreRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
  }, [router]);

  return (
    <div className="shell" style={{ padding: "64px 0", textAlign: "center" }}>
      <p style={{ color: "var(--muted)" }}>Đang chuyển hướng về trang chủ...</p>
    </div>
  );
}
