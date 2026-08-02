import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Performance",
};

export default function PerformancePage() {
  return <ModulePlaceholder module="performance" />;
}
