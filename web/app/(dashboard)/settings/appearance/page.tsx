import type { Metadata } from "next";

import { AppearanceSettings } from "@/features/settings/appearance";

export const metadata: Metadata = {
  title: "Appearance",
};

export default function AppearanceSettingsPage() {
  return <AppearanceSettings />;
}
