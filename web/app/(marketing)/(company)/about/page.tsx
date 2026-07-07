import type { Metadata } from "next";

import { About } from "@/features/company/about";

export const metadata: Metadata = {
  title: "About",
  description:
    "Guardrail Hub is built by a small team of security and devtools engineers making continuous, evidence-backed security available to every team.",
};

export default function AboutPage() {
  return <About />;
}
