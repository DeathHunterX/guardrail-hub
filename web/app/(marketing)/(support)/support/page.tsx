import type { Metadata } from "next";

import { Support } from "@/features/support/support";

export const metadata: Metadata = {
  title: "Support",
  description:
    "Answers to common Guardrail Hub questions — getting started, scans, billing, team access, integrations — plus direct email support.",
};

export default function SupportPage() {
  return <Support />;
}
