import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Integrations",
};

export default function IntegrationsPage() {
  return <ModulePlaceholder module="integrations" />;
}
