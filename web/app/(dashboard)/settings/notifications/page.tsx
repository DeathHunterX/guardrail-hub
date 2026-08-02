import type { Metadata } from "next";

import { NotificationsSettings } from "@/features/settings/notifications";

export const metadata: Metadata = {
  title: "Notifications",
};

export default function NotificationsSettingsPage() {
  return <NotificationsSettings />;
}
