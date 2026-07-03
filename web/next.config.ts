import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The landing page ships as fully static output; images are local SVGs
  // optimized at build time, so no remote patterns are required yet.
  images: {
    formats: ["image/avif", "image/webp"],
  },
};

export default nextConfig;
