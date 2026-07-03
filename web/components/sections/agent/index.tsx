import { ShieldCheck } from "lucide-react";

import { SectionShell } from "@/components/shared/section-shell";

import { agentCopy, agentStats, capabilities, guardrailNote } from "./agent.data";
import { AgentDemo } from "./agent-demo";

/** AI Agent Experience (spec §9): demo left, copy right — reversed hero rhythm. */
export function Agent() {
  return (
    <SectionShell
      id="agent"
      eyebrow={agentCopy.eyebrow}
      title={agentCopy.title}
      lede={agentCopy.lede}
      align="left"
    >
      <div className="grid items-center gap-12 lg:grid-cols-12">
        <div data-reveal className="lg:col-span-7">
          <AgentDemo />
        </div>
        <div className="lg:col-span-5">
          <ul className="space-y-6">
            {capabilities.map((capability) => (
              <li key={capability.lead} data-reveal className="flex gap-4">
                <span className="icon-tile">
                  <capability.icon className="size-5" aria-hidden />
                </span>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  <strong className="font-semibold text-foreground">
                    {capability.lead}
                  </strong>{" "}
                  {capability.text}
                </p>
              </li>
            ))}
          </ul>

          <dl
            data-reveal
            className="mt-8 grid grid-cols-3 gap-3 border-y py-6"
          >
            {agentStats.map((stat) => (
              <div key={stat.label} className="text-center lg:text-left">
                <dd className="font-mono text-xl font-semibold tracking-tight">
                  {stat.value}
                </dd>
                <dt className="mt-1 text-xs text-muted-foreground">
                  {stat.label}
                </dt>
              </div>
            ))}
          </dl>

          <div
            data-reveal
            className="mt-6 flex gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-4"
          >
            <ShieldCheck className="size-5 shrink-0 text-primary" aria-hidden />
            <p className="text-sm leading-relaxed text-muted-foreground">
              <strong className="font-semibold text-foreground">
                {guardrailNote.title}.
              </strong>{" "}
              {guardrailNote.text}
            </p>
          </div>
        </div>
      </div>
    </SectionShell>
  );
}
