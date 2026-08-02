"use client";

import { Logo } from "@/components/layout/logo";
import { SheetContent, SheetTitle } from "@/components/ui/sheet";

import { SidebarNav } from "./sidebar-nav";

interface AppSidebarSheetContentProps {
  onNavigate: () => void;
}

/** Mobile counterpart of AppSidebar — same nav inside a left sheet. */
export function AppSidebarSheetContent({
  onNavigate,
}: AppSidebarSheetContentProps) {
  return (
    <SheetContent side="left" className="w-72 p-0">
      <SheetTitle className="sr-only">Navigation</SheetTitle>
      <div className="flex h-16 items-center border-b px-5">
        <Logo />
      </div>
      <div className="overflow-y-auto px-3 py-4">
        <SidebarNav onNavigate={onNavigate} />
      </div>
    </SheetContent>
  );
}
