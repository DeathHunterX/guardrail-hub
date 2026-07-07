import { SectionShell } from "@/components/common/section-shell";

import { IntegrationGrid } from "./integration-grid";
import { integrationsCopy } from "./data";
import { OrbitDiagram } from "./orbit-diagram";

/** Security Tool Integrations (spec §10): orbit theater + accessible grid. */
export function Integrations() {
  return (
    <SectionShell
      id="integrations"
      eyebrow={integrationsCopy.eyebrow}
      title={integrationsCopy.title}
      lede={integrationsCopy.lede}
    >
      <div data-reveal>
        <OrbitDiagram />
      </div>
      <div data-reveal>
        <IntegrationGrid />
      </div>
    </SectionShell>
  );
}
