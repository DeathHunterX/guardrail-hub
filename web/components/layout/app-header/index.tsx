"use client";

import { Menu, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { CommandMenu } from "@/components/common/command-menu";
import { ThemeToggle } from "@/components/common/theme-toggle";
import { AppSidebarSheetContent } from "@/components/layout/app-sidebar/sheet-content";
import { Button } from "@/components/ui/button";
import { Sheet, SheetTrigger } from "@/components/ui/sheet";

import { NotificationsMenu } from "./notifications-menu";
import { OrgSwitcher } from "./org-switcher";
import { UserMenu } from "./user-menu";

/**
 * Top navigation of the authenticated shell: mobile nav trigger, org
 * switcher, global search (⌘K), theme toggle, notifications, user menu.
 */
export function AppHeader() {
  const [commandOpen, setCommandOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);

  // Global ⌘K / Ctrl+K shortcut, matching the marketing header.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setCommandOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <header className="glass-surface sticky top-0 z-40 flex h-16 items-center gap-2 border-x-0 border-t-0 px-4 sm:px-6">
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Open navigation"
          >
            <Menu aria-hidden="true" />
          </Button>
        </SheetTrigger>
        <AppSidebarSheetContent onNavigate={() => setSheetOpen(false)} />
      </Sheet>

      <OrgSwitcher />

      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="outline"
          className="h-9 w-9 justify-center p-0 text-muted-foreground sm:w-56 sm:justify-start sm:px-3"
          onClick={() => setCommandOpen(true)}
        >
          <Search aria-hidden="true" />
          <span className="hidden flex-1 text-left text-sm font-normal sm:inline">
            Search…
          </span>
          <kbd className="hidden rounded border bg-muted px-1.5 font-mono text-[10px] text-muted-foreground sm:inline">
            ⌘K
          </kbd>
        </Button>
        <ThemeToggle />
        <NotificationsMenu />
        <UserMenu />
      </div>

      <CommandMenu
        scope="app"
        open={commandOpen}
        onOpenChange={setCommandOpen}
      />
    </header>
  );
}
