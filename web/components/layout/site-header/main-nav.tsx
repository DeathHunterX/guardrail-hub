"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";
import { navigation } from "@/content/site";
import type { NavMegaItem } from "@/types/navigation";
import { cn } from "@/lib/utils";

import { useActiveSection } from "@/hooks/use-active-section";

function MegaMenuItem({ item }: { item: NavMegaItem }) {
  return (
    <li>
      <NavigationMenuLink asChild>
        <Link
          href={item.href}
          className="group flex gap-3 rounded-lg p-3 transition-colors hover:bg-accent focus:bg-accent focus:outline-none"
        >
          <span className="icon-tile size-9 rounded-md">
            <item.icon className="size-4" aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-medium leading-tight">
              {item.label}
            </span>
            <span className="mt-1 line-clamp-2 block text-sm leading-snug text-muted-foreground">
              {item.description}
            </span>
          </span>
        </Link>
      </NavigationMenuLink>
    </li>
  );
}

/** Desktop navigation: mega-dropdowns for Product/Solutions + direct links. */
export function MainNav() {
  const pathname = usePathname();
  const onLanding = pathname === "/";

  // Links can carry a landing-only anchor (e.g. Pricing -> #pricing); the
  // active indicator tracks whichever links resolve to an anchor here.
  const resolvedLinks = useMemo(
    () =>
      navigation.links.map((link) => ({
        ...link,
        href: onLanding && link.landingHref ? link.landingHref : link.href,
      })),
    [onLanding],
  );
  const anchorIds = useMemo(
    () =>
      resolvedLinks
        .filter((link) => link.href.startsWith("#"))
        .map((link) => link.href.slice(1)),
    [resolvedLinks],
  );
  const activeId = useActiveSection(anchorIds);

  return (
    <NavigationMenu aria-label="Main">
      <NavigationMenuList>
        {navigation.groups.map((group) => (
          <NavigationMenuItem key={group.label}>
            <NavigationMenuTrigger>{group.label}</NavigationMenuTrigger>
            <NavigationMenuContent>
              <ul className="grid w-[480px] gap-1 p-3 md:grid-cols-2">
                {group.items.map((item) => (
                  <MegaMenuItem key={`${group.label}-${item.label}`} item={item} />
                ))}
              </ul>
            </NavigationMenuContent>
          </NavigationMenuItem>
        ))}
        {resolvedLinks.map((link) => (
          <NavigationMenuItem key={link.label}>
            <NavigationMenuLink asChild>
              {link.external ? (
                <a
                  href={link.href}
                  target="_blank"
                  rel="noreferrer"
                  className={cn(navigationMenuTriggerStyle(), "gap-1")}
                >
                  {link.label}
                  <ArrowUpRight
                    className="size-3 text-muted-foreground"
                    aria-hidden
                  />
                </a>
              ) : (
                <Link
                  href={link.href}
                  className={cn(navigationMenuTriggerStyle(), "relative")}
                >
                  {link.label}
                  <span
                    aria-hidden
                    className={cn(
                      "absolute -bottom-0.5 left-1/2 size-1 -translate-x-1/2 rounded-full bg-primary transition-transform duration-200",
                      activeId === link.href.slice(1) ? "scale-100" : "scale-0",
                    )}
                  />
                </Link>
              )}
            </NavigationMenuLink>
          </NavigationMenuItem>
        ))}
      </NavigationMenuList>
    </NavigationMenu>
  );
}
