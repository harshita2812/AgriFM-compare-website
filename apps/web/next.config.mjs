const apiOrigin = process.env.AGRIFM_API_ORIGIN || "http://127.0.0.1:8000";

/** @type {import("next").NextConfig} */
const nextConfig = {
  experimental: {
    externalDir: true,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
