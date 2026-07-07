import type { Metadata } from "next";

import { LegalArticle } from "@/components/common/legal-article";
import { termsDoc } from "@/features/legal/terms/data";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "The agreement governing use of the Guardrail Hub website, early-access program, and platform.",
};

export default function TermsPage() {
  return <LegalArticle doc={termsDoc} />;
}
