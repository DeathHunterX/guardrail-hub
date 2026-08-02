import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Reports",
};

export default function ReportsPage() {
  return <ModulePlaceholder module="reports" />;
}
