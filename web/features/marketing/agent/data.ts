import { BrainCircuit, MessageSquare, ShieldQuestion } from "lucide-react";

import type { AgentStat, Capability, Scenario } from "./types";

export const agentCopy = {
  eyebrow: "The agent",
  title: "Security expertise, on demand.",
  lede: "Every request becomes a scoped plan, an orchestrated run, and an explanation a human can act on.",
} as const;

export const capabilities: Capability[] = [
  {
    icon: BrainCircuit,
    lead: "Understands intent.",
    text: "“Check the payment flow for auth issues” becomes a scoped, multi-scanner plan.",
  },
  {
    icon: MessageSquare,
    lead: "Explains everything.",
    text: "Every finding comes with plain-language impact and a suggested fix.",
  },
  {
    icon: ShieldQuestion,
    lead: "Acts with guardrails.",
    text: "Read-only by default; destructive tests require explicit approval.",
  },
];

export const scenarios: Scenario[] = [
  {
    id: "staging",
    chip: "Scan my staging environment",
    user: "Scan my staging environment",
    blocks: [
      {
        type: "text",
        text: "On it. staging.acme.dev exposes 3 services — I'll run DAST on the API, dependency checks on both workers, and skip destructive tests.",
      },
      { type: "tools", tools: ["ZAP", "Trivy", "Semgrep"] },
      { type: "badge", badge: { label: "Scan complete — 2 medium, 0 critical", variant: "success" } },
    ],
  },
  {
    id: "cve",
    chip: "Are we exposed to CVE-2026-1337?",
    user: "Are we exposed to CVE-2026-1337?",
    blocks: [
      {
        type: "text",
        text: "CVE-2026-1337 affects fastjson < 2.0.4. I checked every lockfile and container image in your org:",
      },
      {
        type: "table",
        rows: [
          { label: "payments-svc", value: "not affected" },
          { label: "billing-worker", value: "2.0.1 — exposed" },
          { label: "web-frontend", value: "not affected" },
        ],
      },
      { type: "badge", badge: { label: "1 service exposed — fix PR drafted", variant: "warning" } },
    ],
  },
  {
    id: "soc2",
    chip: "Prepare SOC 2 evidence for Q3",
    user: "Prepare SOC 2 evidence for Q3",
    blocks: [
      {
        type: "text",
        text: "Collecting Q3 evidence for CC6.1, CC7.1 and CC7.2 from 214 scan runs. Exporting attestations with timestamps and control mappings.",
      },
      { type: "badge", badge: { label: "Evidence pack ready — 38 artifacts", variant: "success" } },
    ],
  },
  {
    id: "explain",
    chip: "Explain finding #4821 like I'm new",
    user: "Explain finding #4821 like I'm new",
    blocks: [
      {
        type: "text",
        text: "Finding #4821 is a SQL injection: the users endpoint pastes raw input into a database query. An attacker could read other users' data. The fix is a parameterized query — I've prepared the 3-line change.",
      },
      { type: "badge", badge: { label: "Severity: Critical — fix takes ~5 min", variant: "destructive" } },
    ],
  },
  {
    id: "load",
    chip: "Load test the checkout API",
    user: "Load test the checkout API",
    blocks: [
      {
        type: "text",
        text: "Running a JMeter plan against checkout-api on staging: 500 virtual users, 5-minute ramp, abuse-case mix included.",
      },
      {
        type: "table",
        rows: [
          { label: "p95 latency", value: "412 ms" },
          { label: "error rate", value: "0.2%" },
          { label: "throughput", value: "1,840 req/min" },
        ],
      },
      { type: "badge", badge: { label: "Passed — JMeter dashboard exported", variant: "success" } },
    ],
  },
  {
    id: "containers",
    chip: "Audit our container images",
    user: "Audit our container images",
    blocks: [
      {
        type: "text",
        text: "Scanning all 12 production images with Trivy — OS packages, app dependencies, and licenses included.",
      },
      { type: "tools", tools: ["Trivy", "npm audit"] },
      { type: "badge", badge: { label: "3 images need base updates — SBOM attached", variant: "warning" } },
    ],
  },
  {
    id: "e2e",
    chip: "Verify the login flow end-to-end",
    user: "Verify the login flow end-to-end",
    blocks: [
      {
        type: "text",
        text: "Replaying the full login journey with Playwright — MFA, session expiry, and lockout paths included. Results published as an Allure report.",
      },
      { type: "badge", badge: { label: "14/14 checks passed — Allure report ready", variant: "success" } },
    ],
  },
  {
    id: "secrets",
    chip: "Any secrets leaked in the repo?",
    user: "Any secrets leaked in the repo?",
    blocks: [
      {
        type: "text",
        text: "Swept 1,204 commits across 18 branches with Gitleaks. One live AWS key found in scripts/migrate.sh — I've drafted a rotation runbook and a history rewrite plan.",
      },
      { type: "badge", badge: { label: "1 live secret — rotate now", variant: "destructive" } },
    ],
  },
];

export const agentStats: AgentStat[] = [
  { value: "40+", label: "tools orchestrated" },
  { value: "3 min", label: "median full scan" },
  { value: "100%", label: "actions audit-logged" },
];

export const guardrailNote = {
  title: "Built-in guardrails",
  text: "Read-only by default. Destructive tests are gated behind explicit approval, and every agent action lands in an immutable audit log.",
} as const;
