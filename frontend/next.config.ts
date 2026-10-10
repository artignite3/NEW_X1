import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.NEXT_OUTPUT === "export" ? "export" : "standalone",
  reactCompiler: true,
};

export default nextConfig;
