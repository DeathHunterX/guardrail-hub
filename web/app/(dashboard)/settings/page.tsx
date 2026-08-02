import { redirect } from "next/navigation";

import { siteConfig } from "@/config/site";

/** /settings has no content of its own — land on the first section. */
export default function SettingsIndexPage() {
  redirect(siteConfig.app.settings);
}
