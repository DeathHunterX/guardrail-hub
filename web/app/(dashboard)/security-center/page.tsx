import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Security",
};

export default function SecurityPage() {
  return <ModulePlaceholder module="security" />;
}
