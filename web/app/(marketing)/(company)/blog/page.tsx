import type { Metadata } from "next";

import { Blog } from "@/features/company/blog";

export const metadata: Metadata = {
  title: "Blog",
  description:
    "Engineering deep-dives, security research, and progress reports from the team building Guardrail Hub.",
};

export default function BlogPage() {
  return <Blog />;
}
