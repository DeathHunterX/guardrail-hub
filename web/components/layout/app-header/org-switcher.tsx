"use client";

import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn, getInitials } from "@/lib/utils";

import { organizations } from "./header.data";

/**
 * Organization switcher. MOCK: selection is local state until organizations
 * exist server-side; the selected org would scope every data request.
 */
export function OrgSwitcher() {
  const [activeId, setActiveId] = useState(organizations[0]?.id);
  const active = organizations.find((org) => org.id === activeId);

  if (!active) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="h-9 gap-2 px-2 data-[state=open]:bg-accent"
          aria-label={`Organization: ${active.name}`}
        >
          <span className="flex size-6 items-center justify-center rounded-md bg-brand-gradient text-[10px] font-semibold text-white">
            {getInitials(active.name)}
          </span>
          <span className="hidden max-w-32 truncate text-sm font-medium sm:inline">
            {active.name}
          </span>
          <ChevronsUpDown
            className="size-3.5 text-muted-foreground"
            aria-hidden="true"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>Organizations</DropdownMenuLabel>
        {organizations.map((org) => (
          <DropdownMenuItem
            key={org.id}
            onSelect={() => setActiveId(org.id)}
            className="gap-2"
          >
            <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-muted text-[10px] font-semibold">
              {getInitials(org.name)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{org.name}</span>
              <span className="block text-xs text-muted-foreground">
                {org.plan}
              </span>
            </span>
            <Check
              className={cn(
                "size-4",
                org.id === activeId ? "opacity-100" : "opacity-0",
              )}
              aria-hidden="true"
            />
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled className="gap-2">
          <Plus className="size-4" aria-hidden="true" />
          Create organization
          <span className="ml-auto text-xs text-muted-foreground">Soon</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
