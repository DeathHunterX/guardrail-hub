import type { ReactNode } from "react";

import { SettingsNav } from "@/components/layout/settings-nav";

/** Settings area shell: heading + grouped left nav + content pane. */
export default function SettingsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
        Settings
      </h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Manage your account, security, and application preferences.
      </p>
      <div className="mt-8 flex flex-col gap-6 lg:flex-row lg:gap-10">
        <SettingsNav />
        <div className="min-w-0 flex-1 space-y-6">{children}</div>
      </div>
    </div>
  );
}
