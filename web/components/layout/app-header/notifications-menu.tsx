"use client";

import { Bell, BellOff } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { StatusDot } from "@/components/common/status-dot";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatRelativeTime } from "@/lib/utils";

import { initialNotifications } from "./header.data";

/** Notification bell + panel. MOCK data until the notification API ships. */
export function NotificationsMenu() {
  const [notifications, setNotifications] = useState(initialNotifications);
  const count = notifications.length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={
            count > 0 ? `Notifications (${count} unread)` : "Notifications"
          }
        >
          <Bell aria-hidden="true" />
          {count > 0 ? (
            <span
              aria-hidden="true"
              className="absolute right-2 top-2 size-2 rounded-full bg-destructive"
            />
          ) : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <p className="text-sm font-semibold">Notifications</p>
          {count > 0 ? (
            <button
              type="button"
              onClick={() => setNotifications([])}
              className="text-xs text-primary underline-offset-4 hover:underline"
            >
              Mark all as read
            </button>
          ) : null}
        </div>
        {count === 0 ? (
          <EmptyState
            icon={BellOff}
            title="All caught up"
            description="New findings, operation results, and worker events will appear here."
            className="py-8"
          />
        ) : (
          <ScrollArea className="max-h-80">
            <ul>
              {notifications.map((notification) => (
                <li
                  key={notification.id}
                  className="flex gap-3 border-b px-4 py-3 last:border-0"
                >
                  <StatusDot
                    status={
                      notification.tone === "neutral"
                        ? "neutral"
                        : notification.tone
                    }
                    className="mt-1.5"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium leading-snug">
                      {notification.title}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {notification.detail}
                    </p>
                  </div>
                  <time className="shrink-0 text-xs text-muted-foreground">
                    {formatRelativeTime(notification.at)}
                  </time>
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
        <div className="border-t px-4 py-2.5 text-center">
          <Link
            href="/settings/notifications"
            className="text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            Notification settings
          </Link>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
