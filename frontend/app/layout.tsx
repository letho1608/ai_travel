import "./globals.css";
import "leaflet/dist/leaflet.css";
import { Inter } from "next/font/google";
import ServiceWorkerRegistration from "@/components/ServiceWorkerRegistration";
import { LocaleProvider } from "@/components/LocaleProvider";
import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";

const inter = Inter({ subsets: ["latin", "vietnamese"], variable: "--font" });

export const metadata = { title: "Mình Đi Đâu Thế", description: "Một kế hoạch du lịch vừa vặn, không cần mở mười tab.", icons: { icon: "/brand/favicon.png", apple: "/brand/favicon.png" } };

export default function RootLayout({children}:{children:React.ReactNode}){
  return (
    <html lang="vi">
      <body className={inter.variable}>
        <LocaleProvider>
          <ServiceWorkerRegistration/>
          <div className="site-wrapper">
            <Navigation/>
            <main className="site-main shell">{children}</main>
            <Footer/>
          </div>
        </LocaleProvider>
      </body>
    </html>
  );
}
