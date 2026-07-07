"use client";

import { Bot, ImagePlus, MessageCircle, Send, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { StatusDot } from "@/components/common/status-dot";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { supportChatCopy } from "./support-chat.data";

interface ChatImage {
  id: string;
  /** Object URL used for the local preview — revoked on unmount. */
  url: string;
  name: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text?: string;
  images?: ChatImage[];
}

let nextId = 0;
/** Stable unique ids for messages and attachments within a session. */
function makeId(prefix: string) {
  nextId += 1;
  return `${prefix}-${nextId}`;
}

/**
 * Floating support chat, mounted on the /support page only. The composer
 * works — text plus image evidence — but interactive replies are a future
 * feature, so every message gets a canned assistant response pointing at
 * email support. The panel is conditionally rendered (not `hidden`): a
 * display class would override the hidden attribute and break the toggle.
 */
export function SupportChat() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [pendingImages, setPendingImages] = useState<ChatImage[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "greeting", role: "assistant", text: supportChatCopy.greeting },
  ]);

  const panelId = useId();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const replyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Every object URL ever created, so unmount can revoke them all — URLs in
  // sent messages must stay alive while the widget is mounted.
  const createdUrlsRef = useRef<string[]>([]);

  // Keep the newest message in view; focus the composer when opening.
  useEffect(() => {
    if (!open) return;
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
    textareaRef.current?.focus();
  }, [messages, open]);

  // Release object URLs and any pending reply timer on unmount.
  useEffect(() => {
    const urls = createdUrlsRef.current;
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
      if (replyTimerRef.current) clearTimeout(replyTimerRef.current);
    };
  }, []);

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []).filter((file) =>
      file.type.startsWith("image/"),
    );
    const images = files.map((file) => {
      const url = URL.createObjectURL(file);
      createdUrlsRef.current.push(url);
      return { id: makeId("img"), url, name: file.name };
    });
    setPendingImages((current) => [...current, ...images]);
    // Allow re-selecting the same file later.
    event.target.value = "";
  };

  const removePendingImage = (id: string) => {
    setPendingImages((current) => {
      const removed = current.find((image) => image.id === id);
      if (removed) {
        URL.revokeObjectURL(removed.url);
        createdUrlsRef.current = createdUrlsRef.current.filter(
          (url) => url !== removed.url,
        );
      }
      return current.filter((image) => image.id !== id);
    });
  };

  const send = useCallback(() => {
    const text = draft.trim();
    if (!text && pendingImages.length === 0) return;

    setMessages((current) => [
      ...current,
      {
        id: makeId("msg"),
        role: "user",
        text: text || undefined,
        images: pendingImages.length ? pendingImages : undefined,
      },
    ]);
    setDraft("");
    setPendingImages([]);

    // Interactive replies are a future feature — answer with the canned note.
    if (replyTimerRef.current) clearTimeout(replyTimerRef.current);
    replyTimerRef.current = setTimeout(() => {
      setMessages((current) => [
        ...current,
        {
          id: makeId("msg"),
          role: "assistant",
          text: supportChatCopy.cannedReply,
        },
      ]);
    }, 600);
  }, [draft, pendingImages]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    send();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  return (
    <>
      {/* Chat panel — mounted only while open so the toggle always works. */}
      {open ? (
        <div
          id={panelId}
          role="dialog"
          aria-label={supportChatCopy.name}
          className="fixed bottom-6 right-4 z-50 flex h-[min(37.5rem,calc(100dvh-6rem))] w-[min(22rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border bg-card shadow-elevation-3 dark:ring-1 dark:ring-white/10"
        >
          {/* Header. */}
          <div className="flex items-center gap-3 border-b bg-muted/40 px-4 py-3">
            <span className="flex size-9 items-center justify-center rounded-full bg-primary/10">
              <Bot className="size-5 text-primary" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold leading-tight">
                {supportChatCopy.name}
              </p>
              <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                <StatusDot status="warning" />
                {supportChatCopy.status}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => setOpen(false)}
              aria-label={supportChatCopy.closeLabel}
            >
              <X aria-hidden />
            </Button>
          </div>

          {/* Preview notice — interaction ships later. */}
          <p className="border-b bg-warning/10 px-4 py-2 text-xs leading-relaxed text-muted-foreground">
            {supportChatCopy.previewNotice}
          </p>

          {/* Message log. */}
          <div
            ref={logRef}
            role="log"
            aria-live="polite"
            className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className={cn(
                  "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
                  message.role === "user"
                    ? "ml-auto rounded-br-md bg-primary text-primary-foreground"
                    : "rounded-bl-md border bg-muted/40 text-foreground",
                )}
              >
                {message.text ? <p>{message.text}</p> : null}
                {message.images?.length ? (
                  <ul
                    className={cn(
                      "grid grid-cols-2 gap-1.5",
                      message.text && "mt-2",
                    )}
                  >
                    {message.images.map((image) => (
                      <li key={image.id}>
                        {/* Object URLs can't go through the Next image optimizer. */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={image.url}
                          alt={image.name}
                          className="aspect-video w-full rounded-lg border object-cover"
                        />
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>

          {/* Pending image previews. */}
          {pendingImages.length > 0 ? (
            <div className="border-t px-4 pt-3">
              <p className="sr-only" aria-live="polite">
                {pendingImages.length === 1
                  ? supportChatCopy.imageNoteSingular
                  : `${pendingImages.length} ${supportChatCopy.imageNotePlural}`}
              </p>
              <ul className="flex flex-wrap gap-2">
                {pendingImages.map((image) => (
                  <li key={image.id} className="relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={image.url}
                      alt={image.name}
                      className="size-14 rounded-lg border object-cover"
                    />
                    <button
                      type="button"
                      onClick={() => removePendingImage(image.id)}
                      aria-label={`Remove ${image.name}`}
                      className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full border bg-background text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <X className="size-3" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* Composer. */}
          <form onSubmit={handleSubmit} className="flex items-end gap-2 p-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={handleFiles}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0 text-muted-foreground hover:text-foreground"
              onClick={() => fileInputRef.current?.click()}
              aria-label={supportChatCopy.attachLabel}
            >
              <ImagePlus aria-hidden />
            </Button>
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder={supportChatCopy.inputPlaceholder}
              aria-label={supportChatCopy.inputPlaceholder}
              className="max-h-28 min-h-9 flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button
              type="submit"
              size="icon"
              className="shrink-0"
              disabled={!draft.trim() && pendingImages.length === 0}
              aria-label={supportChatCopy.sendLabel}
            >
              <Send aria-hidden />
            </Button>
          </form>
        </div>
      ) : null}

      {/* Floating toggle — hidden while the panel is open (the panel anchors
          to the same corner, so a lingering button would just leave a gap). */}
      {!open ? (
        <Button
          size="icon"
          onClick={() => setOpen(true)}
          aria-expanded={open}
          aria-label={supportChatCopy.openLabel}
          className="fixed bottom-6 right-4 z-50 size-12 rounded-full shadow-elevation-3"
        >
          <MessageCircle aria-hidden />
        </Button>
      ) : null}
    </>
  );
}
