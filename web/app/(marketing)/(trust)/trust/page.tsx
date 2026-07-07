import type { Metadata } from "next";

import { TrustCenter } from "@/features/trust/trust-center";

export const metadata: Metadata = {
  title: "Trust Center",
  description:
    "Certifications, security practices, and subprocessors — everything a security review of Guardrail Hub needs, in one place.",
};

export default function TrustPage() {
  return <TrustCenter />;
}
