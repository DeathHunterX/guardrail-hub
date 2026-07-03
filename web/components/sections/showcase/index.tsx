import { SectionShell } from "@/components/shared/section-shell";

import { DashboardMock } from "./dashboard-mock";
import { showcaseCopy } from "./showcase.data";

/** Interactive Product Showcase (spec §8). */
export function Showcase() {
  return (
    <SectionShell
      id="showcase"
      eyebrow={showcaseCopy.eyebrow}
      title={showcaseCopy.title}
      lede={showcaseCopy.lede}
    >
      <div data-reveal>
        <DashboardMock />
      </div>
    </SectionShell>
  );
}
