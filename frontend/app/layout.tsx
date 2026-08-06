import "./globals.css";
import "leaflet/dist/leaflet.css";
import Link from "next/link";
import ServiceWorkerRegistration from "@/components/ServiceWorkerRegistration";
import { LocaleProvider } from "@/components/LocaleProvider";
import Navigation from "@/components/Navigation";

export const metadata = { title: "Mình Đi Đâu Thế", description: "Một kế hoạch Hà Nội vừa vặn, không cần mở mười tab." };
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="vi"><body><LocaleProvider><ServiceWorkerRegistration/><div className="shell"><Navigation/>{children}<footer className="legal-footer"><span>© 2026 Mình Đi Đâu Thế</span><Link href="/terms">Điều khoản</Link><Link href="/privacy">Bảo mật</Link></footer></div></LocaleProvider></body></html>}
