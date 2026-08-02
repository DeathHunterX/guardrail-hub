import type { Metadata } from "next";

import { GeneralSettings } from "@/features/settings/general";

export const metadata: Metadata = {
  title: "General settings",
};

export default function GeneralSettingsPage() {
  return <GeneralSettings />;
}
