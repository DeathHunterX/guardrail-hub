"use client";

import { useCallback } from "react";

import { useLocalStorage } from "@/hooks/use-local-storage";
import { signOut as signOutService } from "@/services/auth.service";
import type { AuthSession, AuthUser } from "@/types/auth";

const SESSION_STORAGE_KEY = "guardrail-hub.session";

/**
 * Client-side session state. MOCK persistence: the session lives in
 * localStorage so the authenticated shell is demonstrable without a backend.
 * Backend integration replaces this with httpOnly-cookie sessions read
 * server-side; the hook's return shape is the stable contract.
 */
export function useSession() {
  const [session, setSession, hydrated] = useLocalStorage<AuthSession | null>(
    SESSION_STORAGE_KEY,
    null,
  );

  const startSession = useCallback(
    (next: AuthSession) => setSession(next),
    [setSession],
  );

  const updateUser = useCallback(
    (patch: Partial<AuthUser>) => {
      if (!session) return;
      setSession({ ...session, user: { ...session.user, ...patch } });
    },
    [session, setSession],
  );

  const endSession = useCallback(async () => {
    await signOutService();
    setSession(null);
  }, [setSession]);

  return {
    session,
    /** False during SSR/first paint — gate redirects on this to avoid flicker. */
    hydrated,
    startSession,
    updateUser,
    endSession,
  } as const;
}
