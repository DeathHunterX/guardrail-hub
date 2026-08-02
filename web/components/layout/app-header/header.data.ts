/**
 * Chrome-level demo data for the app header (mirrors site-footer's colocated
 * footer.data.ts). MOCK: organizations and notifications come from the
 * backend once it ships — shapes here are the display contract.
 */

export interface Organization {
  id: string;
  name: string;
  plan: "Free" | "Team" | "Enterprise";
}

export const organizations: Organization[] = [
  { id: "org_acme", name: "Acme Platform", plan: "Enterprise" },
  { id: "org_acme_staging", name: "Acme Staging", plan: "Team" },
  { id: "org_personal", name: "Personal", plan: "Free" },
];

export interface AppNotification {
  id: string;
  title: string;
  detail: string;
  /** ISO timestamp. */
  at: string;
  tone: "success" | "warning" | "destructive" | "neutral";
}

const hoursAgo = (h: number) =>
  new Date(Date.now() - h * 3_600_000).toISOString();

export const initialNotifications: AppNotification[] = [
  {
    id: "ntf_001",
    title: "Baseline scan completed",
    detail: "api-gateway · 0 new critical findings",
    at: hoursAgo(1),
    tone: "success",
  },
  {
    id: "ntf_002",
    title: "New medium finding",
    detail: "checkout-service · CSP header missing",
    at: hoursAgo(3),
    tone: "warning",
  },
  {
    id: "ntf_003",
    title: "Worker zap-worker-04 offline",
    detail: "Pool capacity reduced to 6/8",
    at: hoursAgo(7),
    tone: "destructive",
  },
  {
    id: "ntf_004",
    title: "Weekly report ready",
    detail: "Security posture report · Jul 20–26",
    at: hoursAgo(26),
    tone: "neutral",
  },
];
