"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { appNavigation } from "@/content/app";
import { cn } from "@/lib/utils";

interface SidebarNavProps {
  /** Called on link click — the mobile sheet closes itself with this. */
  onNavigate?: () => void;
}

/**
 * App navigation list, shared by the desktop sidebar and the mobile sheet.
 * Modules whose backend doesn't exist yet carry a "Soon" chip and route to
 * the shared module-placeholder page.
 */
export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const pathname = usePathname();

  return (
    <nav aria-label="App navigation" className="flex flex-1 flex-col gap-6">
      {appNavigation.map((section, index) => (
        <div key={section.label ?? `section-${index}`}>
          {section.label ? (
            <p className="mb-2 px-3 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              {section.label}
            </p>
          ) : null}
          <ul className="space-y-0.5">
            {section.items.map((item) => {
              const active =
                pathname === item.href ||
                (item.href !== "/dashboard" &&
                  pathname.startsWith(`${item.href}/`)) ||
                (item.href === "/settings/profile" &&
                  pathname.startsWith("/settings"));
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    onClick={onNavigate}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-accent font-medium text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                    )}
                  >
                    <item.icon className="size-4 shrink-0" aria-hidden="true" />
                    <span className="truncate">{item.label}</span>
                    {item.planned ? (
                      <Badge
                        variant="secondary"
                        className="ml-auto px-1.5 text-[10px]"
                      >
                        Soon
                      </Badge>
                    ) : null}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
