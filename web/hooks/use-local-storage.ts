"use client";

import { useCallback, useRef, useSyncExternalStore } from "react";

import { useMounted } from "@/hooks/use-mounted";

/**
 * Hydration-safe localStorage state. The server and the first client render
 * always see `initialValue`; the stored value is applied after mount so
 * markup never mismatches.
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
): readonly [T, (value: T) => void, boolean] {
  // Holds the last `set()` value when persisting to localStorage failed
  // (private mode, quota, etc.), so in-memory state still reflects it even
  // though the write didn't stick.
  const overrideRef = useRef<{ key: string; value: T } | null>(null);
  const listenerRef = useRef<(() => void) | null>(null);

  const subscribe = useCallback((onChange: () => void) => {
    listenerRef.current = onChange;
    return () => {
      listenerRef.current = null;
    };
  }, []);

  const getSnapshot = useCallback((): T => {
    if (overrideRef.current?.key === key) {
      return overrideRef.current.value;
    }
    try {
      const stored = window.localStorage.getItem(key);
      return stored !== null ? (JSON.parse(stored) as T) : initialValue;
    } catch {
      return initialValue;
    }
  }, [key, initialValue]);

  const getServerSnapshot = useCallback(() => initialValue, [initialValue]);

  const value = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const set = useCallback(
    (next: T) => {
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
        overrideRef.current = null;
      } catch {
        // Persisting is best-effort; in-memory state still updates.
        overrideRef.current = { key, value: next };
      }
      listenerRef.current?.();
    },
    [key],
  );

  const hydrated = useMounted();

  return [value, set, hydrated] as const;
}
