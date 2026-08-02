"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";

import { DashboardCard } from "@/components/common/dashboard-card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSession } from "@/hooks/use-session";
import { getInitials } from "@/lib/utils";
import { updateProfile } from "@/services/account.service";
import type { ServiceError } from "@/types/api";

import { languageOptions, timezoneOptions } from "./data";

export function ProfileSettings() {
  const { session, updateUser } = useSession();
  const user = session?.user;

  const [fullName, setFullName] = useState(user?.fullName ?? "");
  const [timezone, setTimezone] = useState(user?.timezone ?? "UTC");
  const [language, setLanguage] = useState(user?.language ?? "en");
  const [nameError, setNameError] = useState<string | null>(null);
  const [error, setError] = useState<ServiceError | null>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);

  if (!user) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaved(false);
    setError(null);
    if (fullName.trim().length < 2) {
      setNameError("Enter your full name.");
      return;
    }
    setNameError(null);
    setPending(true);
    const result = await updateProfile({
      fullName: fullName.trim(),
      timezone,
      language,
    });
    setPending(false);
    if (result.ok) {
      updateUser(result.data);
      setSaved(true);
    } else {
      setError(result.error);
    }
  };

  return (
    <DashboardCard
      title="Profile"
      description="How you appear across your workspace."
    >
      {error ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="size-4" aria-hidden="true" />
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <div className="flex items-center gap-4">
          <Avatar className="size-16">
            {user.avatarUrl ? (
              <AvatarImage src={user.avatarUrl} alt="" />
            ) : null}
            <AvatarFallback className="bg-primary/10 text-lg font-semibold text-primary">
              {getInitials(user.fullName)}
            </AvatarFallback>
          </Avatar>
          <div>
            <Button type="button" variant="outline" size="sm" disabled>
              Change avatar
            </Button>
            {/* Placeholder for backend integration: avatar upload needs the files API. */}
            <p className="mt-1.5 text-xs text-muted-foreground">
              Avatar upload arrives with the files API.
            </p>
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="profile-name">Full name</Label>
            <Input
              id="profile-name"
              autoComplete="name"
              value={fullName}
              disabled={pending}
              aria-invalid={nameError ? true : undefined}
              aria-describedby={nameError ? "profile-name-error" : undefined}
              onChange={(event) => {
                setFullName(event.target.value);
                setSaved(false);
              }}
            />
            {nameError ? (
              <p id="profile-name-error" className="text-xs text-destructive">
                {nameError}
              </p>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="profile-email">Email</Label>
            <Input
              id="profile-email"
              type="email"
              value={user.email}
              readOnly
              disabled
              aria-describedby="profile-email-hint"
            />
            <p
              id="profile-email-hint"
              className="text-xs text-muted-foreground"
            >
              Email changes require verification — contact support.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="profile-timezone">Timezone</Label>
            <Select
              value={timezone}
              onValueChange={(value) => {
                setTimezone(value);
                setSaved(false);
              }}
              disabled={pending}
            >
              <SelectTrigger id="profile-timezone">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {timezoneOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="profile-language">Language</Label>
            <Select
              value={language}
              onValueChange={(value) => {
                setLanguage(value);
                setSaved(false);
              }}
              disabled={pending}
            >
              <SelectTrigger id="profile-language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {languageOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={pending}>
            {pending ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : null}
            Save changes
          </Button>
          {saved ? (
            <p role="status" className="text-sm text-success">
              Changes saved.
            </p>
          ) : null}
        </div>
      </form>
    </DashboardCard>
  );
}
