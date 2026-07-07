"use client";

import {
  ArrowRight,
  Bot,
  CalendarClock,
  FileText,
  Github,
  History,
  Monitor,
  Moon,
  Sun,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useCallback } from "react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { siteConfig } from "@/config/site";
import { externalLinks } from "@/constants/external-links";
import { navigation } from "@/content/site";

interface CommandMenuProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Global command palette (⌘K). Lazy-loaded by HeaderActions on first intent,
 * so cmdk never enters the initial bundle.
 */
export function CommandMenu({ open, onOpenChange }: CommandMenuProps) {
  const router = useRouter();
  const { setTheme } = useTheme();

  const run = useCallback(
    (action: () => void) => {
      onOpenChange(false);
      action();
    },
    [onOpenChange],
  );

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search pages, docs, actions…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {navigation.groups.flatMap((group) =>
            group.items.map((item) => (
              <CommandItem
                key={item.href}
                value={`${group.label} ${item.label}`}
                onSelect={() => run(() => router.push(item.href))}
              >
                <item.icon aria-hidden />
                {item.label}
              </CommandItem>
            )),
          )}
        </CommandGroup>
        <CommandGroup heading="Resources">
          <CommandItem
            onSelect={() =>
              run(() => window.open(externalLinks.docs, "_blank", "noopener"))
            }
          >
            <FileText aria-hidden />
            Documentation
          </CommandItem>
          <CommandItem
            onSelect={() =>
              run(() =>
                window.open(externalLinks.github, "_blank", "noopener"),
              )
            }
          >
            <Github aria-hidden />
            GitHub repository
          </CommandItem>
          <CommandItem
            onSelect={() =>
              run(() =>
                window.open(
                  `${externalLinks.github}/releases`,
                  "_blank",
                  "noopener",
                ),
              )
            }
          >
            <History aria-hidden />
            Changelog
          </CommandItem>
        </CommandGroup>
        <CommandGroup heading="Get started">
          <CommandItem
            onSelect={() => run(() => router.push(siteConfig.app.signUp))}
          >
            <ArrowRight aria-hidden />
            Start Free
          </CommandItem>
          <CommandItem
            onSelect={() => run(() => router.push(siteConfig.app.bookDemo))}
          >
            <CalendarClock aria-hidden />
            Book Demo
          </CommandItem>
          <CommandItem onSelect={() => run(() => router.push("#agent"))}>
            <Bot aria-hidden />
            Meet the AI agent
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Theme">
          <CommandItem onSelect={() => run(() => setTheme("light"))}>
            <Sun aria-hidden />
            Light
          </CommandItem>
          <CommandItem onSelect={() => run(() => setTheme("dark"))}>
            <Moon aria-hidden />
            Dark
          </CommandItem>
          <CommandItem onSelect={() => run(() => setTheme("system"))}>
            <Monitor aria-hidden />
            System
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
