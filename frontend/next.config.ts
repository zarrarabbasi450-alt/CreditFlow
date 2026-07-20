import type { NextConfig } from "next";
import path from "node:path";
const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  eslint: { ignoreDuringBuilds: true },
  webpack: (config, { isServer }) => {
    if (isServer) config.resolve.alias["msw/browser"] = path.resolve("src/mocks/browser-noop.ts");
    return config;
  },
};
export default nextConfig;
