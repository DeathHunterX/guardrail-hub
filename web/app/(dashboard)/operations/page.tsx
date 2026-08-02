import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Operations",
};

export default function OperationsPage() {
  return <ModulePlaceholder module="operations" />;
}
