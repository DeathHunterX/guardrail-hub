import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Help",
};

export default function HelpPage() {
  return <ModulePlaceholder module="help" />;
}
