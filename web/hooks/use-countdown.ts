"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Seconds countdown for resend timers (OTP step). `restart` arms the timer;
 * `remaining === 0` means the action is available again.
 */
export function useCountdown(initialSeconds: number) {
  const [remaining, setRemaining] = useState(initialSeconds);

  useEffect(() => {
    if (remaining <= 0) return;
    const timer = setInterval(
      () => setRemaining((current) => Math.max(0, current - 1)),
      1000,
    );
    return () => clearInterval(timer);
  }, [remaining]);

  const restart = useCallback((seconds: number) => setRemaining(seconds), []);

  return { remaining, restart } as const;
}
