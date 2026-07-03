"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Hydration-safe localStorage state. The server and the first client render
 * always see `initialValue`; the stored value is applied after mount so
 * markup never mismatches.
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): readonly [T, (value: T) => void, boolean] {
  const [value, setValue] = useState<T>(initialValue);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(key);
      if (stored !== null) {
        setValue(JSON.parse(stored) as T);
      }
    } catch {
      // Storage unavailable (private mode, blocked) — keep the initial value.
    }
    setHydrated(true);
  }, [key]);

  const set = useCallback(
    (next: T) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // Persisting is best-effort; in-memory state still updates.
      }
    },
    [key],
  );

  return [value, set, hydrated] as const;
}
