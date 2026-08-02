"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";

import { siteConfig } from "@/config/site";
import { useSession } from "@/hooks/use-session";

/**
 * Client-side route guard for the authenticated shell. With the MOCK session
 * living in localStorage this is the only enforcement point; backend
 * integration moves the real check server-side (httpOnly cookie + proxy)
 * and this component keeps only the redirect UX.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { session, hydrated } = useSession();

  useEffect(() => {
    if (hydrated && !session) router.replace(siteConfig.app.signIn);
  }, [hydrated, session, router]);

  if (!hydrated || !session) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Loader2
          className="size-6 animate-spin text-muted-foreground"
          aria-hidden="true"
        />
        <span className="sr-only">Checking your session…</span>
      </div>
    );
  }

  return <>{children}</>;
}
