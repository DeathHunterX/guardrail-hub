import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Artifacts",
};

export default function ArtifactsPage() {
  return <ModulePlaceholder module="artifacts" />;
}
