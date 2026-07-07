import type { Metadata } from "next";

import { Security } from "@/features/trust/security";

export const metadata: Metadata = {
  title: "Responsible Disclosure",
  description:
    "How to report a security vulnerability in Guardrail Hub — scope, response timelines, and our safe harbor commitment.",
};

export default function SecurityPage() {
  return <Security />;
}
