import type { Metadata } from "next";

import { Changelog } from "@/features/company/changelog";

export const metadata: Metadata = {
  title: "Changelog",
  description:
    "Every Guardrail Hub release in the open — overviews, key updates, and links to the full release notes.",
};

export default function ChangelogPage() {
  return <Changelog />;
}
