import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://43.205.195.227:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
