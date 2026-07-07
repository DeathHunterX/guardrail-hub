import type { Metadata } from "next";

import { Careers } from "@/features/company/careers";

export const metadata: Metadata = {
  title: "Careers",
  description:
    "Join the small, remote-first team building Guardrail Hub — an AI-powered security validation platform, developed in the open.",
};

export default function CareersPage() {
  return <Careers />;
}
