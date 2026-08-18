const isDev = process.env.NODE_ENV !== "production";
const scriptSrc = isDev
  ? "'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://apis.google.com https://www.gstatic.com"
  : "'self' 'unsafe-inline' https://accounts.google.com https://apis.google.com https://www.gstatic.com";
const apiOrigin = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const connectSrc = [
  "'self'",
  ...Array.from({ length: 11 }, (_, index) => `http://localhost:${8000 + index}`),
  ...Array.from({ length: 11 }, (_, index) => `http://127.0.0.1:${8000 + index}`),
  "https:",
].join(" ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "Content-Security-Policy", value: `default-src 'self'; script-src ${scriptSrc}; style-src 'self' 'unsafe-inline' https://accounts.google.com https://www.gstatic.com; img-src 'self' data: blob: https://*.tile.openstreetmap.org https:; connect-src ${connectSrc}; font-src 'self' data:; frame-src https://accounts.google.com https://www.gstatic.com https://*.google.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  experimental: {
    proxyTimeout: 300000,
  },
  async headers() { return [{ source: "/(.*)", headers: securityHeaders }]; },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiOrigin}/api/:path*` },
      { source: "/health", destination: `${apiOrigin}/health` },
      { source: "/ready", destination: `${apiOrigin}/ready` },
    ];
  },
};
export default nextConfig;
