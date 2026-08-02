import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/common/theme-toggle";
import { SkipLink } from "@/components/layout/skip-link";

/**
 * Auth shell: centered card on the landing page's ambient canvas (dot grid +
 * brand glow), with a way back home and the theme toggle. No marketing chrome
 * — the card is the whole story.
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden">
      {/* Ambient backdrop, faded toward the edges like the hero. */}
      <div
        aria-hidden="true"
        className="dot-grid-bg absolute inset-0 -z-20 [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,black,transparent)]"
      />
      <div
        aria-hidden="true"
        className="absolute left-1/2 top-0 -z-10 h-80 w-[36rem] -translate-x-1/2 -translate-y-1/3 rounded-full bg-brand-gradient blur-3xl"
        style={{ opacity: "var(--glow-opacity)" }}
      />

      <SkipLink />

      <header className="flex items-center justify-between px-4 py-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back to home
        </Link>
        <ThemeToggle />
      </header>

      <main
        id="content"
        className="flex flex-1 items-center justify-center px-4 py-10 sm:px-6"
      >
        {children}
      </main>

      <footer className="flex items-center justify-center gap-4 px-4 pb-6 text-xs text-muted-foreground">
        <Link href="/terms" className="transition-colors hover:text-foreground">
          Terms
        </Link>
        <Link
          href="/privacy"
          className="transition-colors hover:text-foreground"
        >
          Privacy
        </Link>
        <Link
          href="/support"
          className="transition-colors hover:text-foreground"
        >
          Support
        </Link>
      </footer>
    </div>
  );
}
