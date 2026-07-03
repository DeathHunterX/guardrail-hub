"use client";

import { useEffect, useState } from "react";

/**
 * Returns true after the component has mounted on the client. Used to gate
 * theme-dependent rendering (e.g. the toggle's current icon) so server and
 * client markup never mismatch.
 */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return mounted;
}
