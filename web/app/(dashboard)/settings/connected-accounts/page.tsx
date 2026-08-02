import type { Metadata } from "next";

import { ConnectedAccountsSettings } from "@/features/settings/connected-accounts";

export const metadata: Metadata = {
  title: "Connected accounts",
};

export default function ConnectedAccountsSettingsPage() {
  return <ConnectedAccountsSettings />;
}
