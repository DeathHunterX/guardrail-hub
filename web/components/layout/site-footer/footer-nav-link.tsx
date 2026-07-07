"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { FooterLink } from "./footer.data";

/**
 * Internal footer link with landing-page awareness: a link that carries a
 * `landingHref` scrolls to its section while on "/", and navigates to its
 * dedicated page from anywhere else (e.g. Pricing).
 */
export function FooterNavLink({ link }: { link: FooterLink }) {
  const pathname = usePathname();
  const href =
    pathname === "/" && link.landingHref ? link.landingHref : link.href;

  return (
    <Link
      href={href}
      className="inline-block text-muted-foreground transition-all hover:translate-x-0.5 hover:text-foreground motion-reduce:hover:translate-x-0"
    >
      {link.label}
    </Link>
  );
}
