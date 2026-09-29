import type { NextConfig } from "next";

// Browser requests use relative /api/* paths. Next.js proxies them to
// FastAPI internally, so port 8000 is never exposed to the browser.
// BACKEND_URL is server-side only (never NEXT_PUBLIC_*).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
