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
  // Caches the parsed value against the raw string it came from, so
  // getSnapshot returns the same reference when localStorage hasn't
  // actually changed — JSON.parse builds a new object every call otherwise,
  // and useSyncExternalStore treats that as an infinite loop.
  const parsedRef = useRef<{ raw: string | null; value: T } | null>(null);

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
    let raw: string | null;
    try {
      raw = window.localStorage.getItem(key);
    } catch {
      return initialValue;
    }
    if (parsedRef.current?.raw === raw) {
      return parsedRef.current.value;
    }
    let value: T;
    try {
      value = raw !== null ? (JSON.parse(raw) as T) : initialValue;
    } catch {
      value = initialValue;
    }
    parsedRef.current = { raw, value };
    return value;
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
