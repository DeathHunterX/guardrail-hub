import type { Metadata } from "next";

import { Overview } from "@/features/dashboard/overview";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Your security and performance operations at a glance.",
};

export default function DashboardPage() {
  return <Overview />;
}
