import type { Metadata } from "next";

import { LegalArticle } from "@/components/common/legal-article";
import { privacyDoc } from "@/features/legal/privacy/data";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How Guardrail Hub collects, uses, and protects personal data across our website and platform.",
};

export default function PrivacyPage() {
  return <LegalArticle doc={privacyDoc} />;
}
