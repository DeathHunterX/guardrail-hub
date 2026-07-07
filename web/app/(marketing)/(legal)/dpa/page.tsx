import type { Metadata } from "next";

import { LegalArticle } from "@/components/common/legal-article";
import { dpaDoc } from "@/features/legal/dpa/data";

export const metadata: Metadata = {
  title: "Data Processing Addendum",
  description:
    "The processor terms that apply when Guardrail Hub processes personal data contained in Customer Content.",
};

export default function DpaPage() {
  return <LegalArticle doc={dpaDoc} />;
}
