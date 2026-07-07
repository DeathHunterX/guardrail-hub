import { Container } from "@/components/common/container";
import { RevealScope } from "@/components/effects/reveal-scope";

import { NodeGraph } from "./node-graph";
import { nodes, outputs, workflowCopy } from "./data";

/**
 * Solution Workflow (spec §6). The visual graph is aria-hidden; this ordered
 * list is the accessible source of truth for the pipeline stages and the
 * native tool outputs attached to the report.
 */
function WorkflowStagesList() {
  return (
    <ol className="sr-only">
      {nodes.map((node) => (
        <li key={node.id}>
          {node.label} — {node.role}
        </li>
      ))}
      {outputs.map((output) => (
        <li key={output.id}>
          {output.label} — {output.role}
        </li>
      ))}
    </ol>
  );
}

export function Workflow() {
  return (
    <section id="workflow" aria-labelledby="workflow-heading" className="py-12 md:py-14">
      <Container>
        <RevealScope>
          <div className="mx-auto max-w-3xl text-center">
            <p
              data-reveal
              className="text-[0.8125rem] font-medium uppercase tracking-widest text-muted-foreground"
            >
              {workflowCopy.eyebrow}
            </p>
            <h2
              data-reveal
              id="workflow-heading"
              className="mt-3 text-balance text-heading-2"
            >
              {workflowCopy.title}
            </h2>
            <p
              data-reveal
              className="mx-auto mt-4 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground"
            >
              {workflowCopy.lede}
            </p>
          </div>
        </RevealScope>
        <WorkflowStagesList />
        <NodeGraph />
      </Container>
    </section>
  );
}
