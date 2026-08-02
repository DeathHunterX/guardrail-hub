import type { Metadata } from "next";

import { EnterpriseSettings } from "@/features/settings/enterprise";

export const metadata: Metadata = {
  title: "Enterprise identity",
};

export default function EnterpriseSettingsPage() {
  return <EnterpriseSettings />;
}
