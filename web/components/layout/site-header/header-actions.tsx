 "use client";

import { Search } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { GitHubStarsButton } from "@/components/common/github-stars-button";
import { ThemeToggle } from "@/components/common/theme-toggle";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";

// The command palette (cmdk) stays out of the initial bundle; it loads on
// first intent — ⌘K or a click on the search button (architecture §2).
const CommandMenu = dynamic(
  () =>
    import("@/components/common/command-menu").then((mod) => mod.CommandMenu),
  { ssr: false },
);

interface HeaderActionsProps {
  stars: number | null;
}

/** Right-hand header cluster: GitHub, search/⌘K, theme, auth CTAs. */
export function HeaderActions({ stars }: HeaderActionsProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuEngaged, setMenuEngaged] = useState(false);

  const openMenu = useCallback(() => {
    setMenuEngaged(true);
    setMenuOpen(true);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        openMenu();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [openMenu]);

  return (
    <div className="flex items-center gap-2">
      <span data-header-item className="hidden md:inline-flex">
        <GitHubStarsButton stars={stars} />
      </span>
      <span data-header-item className="hidden md:inline-flex">
        <Button
          variant="outline"
          size="sm"
          onClick={openMenu}
          className="gap-2 text-muted-foreground"
          aria-label="Open command menu"
        >
          <Search aria-hidden />
          <span>Search</span>
          <kbd className="pointer-events-none hidden select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium lg:inline-flex">
            ⌘K
          </kbd>
        </Button>
      </span>
      <span data-header-item className="inline-flex">
        <ThemeToggle />
      </span>
      <span data-header-item className="hidden lg:inline-flex">
        <Button asChild variant="ghost" size="sm">
          <Link href={siteConfig.app.signIn}>Sign in</Link>
        </Button>
      </span>
      <span data-header-item className="hidden sm:inline-flex">
        <Button asChild size="sm" className="btn-sheen">
          <Link href={siteConfig.app.signUp}>Start Free</Link>
        </Button>
      </span>
      {menuEngaged ? (
        <CommandMenu open={menuOpen} onOpenChange={setMenuOpen} />
      ) : null}
    </div>
  );
}
