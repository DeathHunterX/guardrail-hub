import type { ReactNode } from "react";

import { AnnouncementBar } from "@/components/layout/announcement-bar";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { SkipLink } from "@/components/layout/skip-link";

/** Marketing shell: announcement + header + page + footer. */
export default function MarketingLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <>
      <SkipLink />
      <AnnouncementBar />
      <SiteHeader />
      <main id="content" className="relative">
        {children}
      </main>
      <SiteFooter />
    </>
  );
}
