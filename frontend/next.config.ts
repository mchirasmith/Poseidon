import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        // The precomputed bundle is rewritten only by a backend run, never per
        // deploy, so it can be cached hard: `fields.bin` alone is several MB.
        source: "/fallback/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};

export default nextConfig;
