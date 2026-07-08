"use client";

import { useSyncExternalStore } from "react";

function subscribe(): () => void {
  return () => {};
}

function getSnapshot(): boolean {
  return true;
}

function getServerSnapshot(): boolean {
  return false;
}

/**
 * Returns true after the component has mounted on the client. Used to gate
 * theme-dependent rendering (e.g. the toggle's current icon) so server and
 * client markup never mismatch.
 */
export function useMounted(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
