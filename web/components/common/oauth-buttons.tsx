"use client";

import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { OAuthProvider } from "@/types/auth";

/**
 * Provider wordmarks. Official brand colors are deliberate literals — brand
 * assets don't re-theme (same rationale as btn-sheen's white highlight).
 */
function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.5 12.27c0-.85-.08-1.66-.22-2.45H12v4.64h6.45a5.52 5.52 0 0 1-2.39 3.62v3h3.87c2.26-2.09 3.57-5.17 3.57-8.81z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.93-2.91l-3.87-3c-1.07.72-2.44 1.14-4.06 1.14-3.12 0-5.77-2.11-6.71-4.95H1.29v3.1A11.99 11.99 0 0 0 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.29 14.28A7.2 7.2 0 0 1 4.91 12c0-.79.14-1.56.38-2.28v-3.1H1.29a12 12 0 0 0 0 10.76l4-3.1z"
      />
      <path
        fill="#EA4335"
        d="M12 4.77c1.76 0 3.34.6 4.58 1.79l3.44-3.44A11.98 11.98 0 0 0 12 0 11.99 11.99 0 0 0 1.29 6.62l4 3.1C6.23 6.88 8.88 4.77 12 4.77z"
      />
    </svg>
  );
}

function MicrosoftIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#F25022" d="M1 1h10.5v10.5H1z" />
      <path fill="#7FBA00" d="M12.5 1H23v10.5H12.5z" />
      <path fill="#00A4EF" d="M1 12.5h10.5V23H1z" />
      <path fill="#FFB900" d="M12.5 12.5H23V23H12.5z" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" fill="#181717">
      <path d="M12 .5A11.5 11.5 0 0 0 .5 12c0 5.09 3.29 9.4 7.86 10.93.58.1.79-.25.79-.56v-2c-3.2.7-3.87-1.54-3.87-1.54-.53-1.33-1.29-1.69-1.29-1.69-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.64 1.58.24 2.75.12 3.04.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.39-5.25 5.67.41.36.78 1.07.78 2.16v3.2c0 .31.21.67.8.56A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5z" />
    </svg>
  );
}

function GitLabIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#E24329" d="M12 22.5 16.25 9.5H7.75L12 22.5z" />
      <path fill="#FC6D26" d="M12 22.5 7.75 9.5H2.9L12 22.5z" />
      <path
        fill="#FCA326"
        d="M2.9 9.5.98 15.32a.87.87 0 0 0 .32.98L12 22.5 2.9 9.5z"
      />
      <path
        fill="#E24329"
        d="M2.9 9.5h4.85L5.75 2.68a.44.44 0 0 0-.84 0L2.9 9.5z"
      />
      <path fill="#FC6D26" d="M12 22.5 16.25 9.5h4.85L12 22.5z" />
      <path
        fill="#FCA326"
        d="M21.1 9.5 23.02 15.32a.87.87 0 0 1-.32.98L12 22.5 21.1 9.5z"
      />
      <path
        fill="#E24329"
        d="M21.1 9.5h-4.85l2.01-6.82a.44.44 0 0 1 .84 0L21.1 9.5z"
      />
    </svg>
  );
}

/** Exported so Connected Accounts (settings) reuses the same branding. */
export const oauthProviders: {
  id: OAuthProvider;
  label: string;
  icon: () => React.JSX.Element;
}[] = [
  { id: "google", label: "Google", icon: GoogleIcon },
  { id: "microsoft", label: "Microsoft", icon: MicrosoftIcon },
  { id: "github", label: "GitHub", icon: GitHubIcon },
  { id: "gitlab", label: "GitLab", icon: GitLabIcon },
];

interface OAuthButtonsProps {
  /** "in" renders "Continue with", "up" renders "Sign up with". */
  intent?: "in" | "up";
  /** Provider currently completing a redirect, disables the whole group. */
  pendingProvider?: OAuthProvider | null;
  disabled?: boolean;
  onSelect: (provider: OAuthProvider) => void;
}

/** OAuth2 provider row shared by sign-in and sign-up. */
export function OAuthButtons({
  intent = "in",
  pendingProvider = null,
  disabled = false,
  onSelect,
}: OAuthButtonsProps) {
  const prefix = intent === "in" ? "Continue with" : "Sign up with";
  return (
    <div className="grid gap-2">
      {oauthProviders.map(({ id, label, icon: Icon }) => (
        <Button
          key={id}
          type="button"
          variant="outline"
          className="w-full justify-center"
          disabled={disabled || pendingProvider !== null}
          onClick={() => onSelect(id)}
        >
          {pendingProvider === id ? (
            <Loader2 className="animate-spin" aria-hidden="true" />
          ) : (
            <Icon />
          )}
          {prefix} {label}
        </Button>
      ))}
    </div>
  );
}
