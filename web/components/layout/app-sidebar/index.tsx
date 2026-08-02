import { Logo } from "@/components/layout/logo";

import { SidebarNav } from "./sidebar-nav";

/**
 * Desktop sidebar for the authenticated shell. Hidden below `lg` — the
 * AppHeader's menu button opens the same SidebarNav in a sheet instead.
 */
export function AppSidebar() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r bg-card/40 lg:flex">
      <div className="flex h-16 items-center border-b px-5">
        <Logo />
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <SidebarNav />
      </div>
    </aside>
  );
}
