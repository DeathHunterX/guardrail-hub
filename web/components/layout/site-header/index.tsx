import { getGitHubStars } from "@/services/github.service";

import { HeaderClient } from "./header-client";

/** Server wrapper ([S->C]): resolves external data, delegates rendering. */
export async function SiteHeader() {
  const stars = await getGitHubStars();
  return <HeaderClient stars={stars} />;
}
