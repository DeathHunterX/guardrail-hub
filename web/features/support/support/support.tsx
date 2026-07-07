import { Mail } from "lucide-react";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { SupportChat } from "./support-chat";
import { escalation, supportCopy, topics } from "./data";

export function Support() {
  const mailtoHref = `mailto:${supportCopy.escalationEmail}?subject=${encodeURIComponent(escalation.emailSubject)}`;

  return (
    <>
      <PageHeader
        eyebrow={supportCopy.eyebrow}
        title={supportCopy.title}
        lede={supportCopy.lede}
      />

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Common cases, grouped by topic. */}
          <div className="grid gap-4 lg:grid-cols-2">
            {topics.map((topic) => (
              <Card data-reveal key={topic.id} className="bg-card/60">
                <CardContent className="p-6">
                  <div className="flex items-start gap-3">
                    <topic.icon
                      className="mt-0.5 size-6 shrink-0 text-primary"
                      aria-hidden
                    />
                    <div>
                      <h2 className="text-sm font-semibold">{topic.title}</h2>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {topic.description}
                      </p>
                    </div>
                  </div>
                  <Accordion type="single" collapsible className="mt-4">
                    {topic.faqs.map((faq) => (
                      <AccordionItem
                        key={faq.question}
                        value={faq.question}
                        className="last:border-b-0"
                      >
                        <AccordionTrigger className="text-left text-sm font-medium">
                          {faq.question}
                        </AccordionTrigger>
                        <AccordionContent className="text-sm leading-relaxed text-muted-foreground">
                          {faq.answer}
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Escalation path for anything not covered above. */}
          <section
            data-reveal
            aria-label={escalation.title}
            className="mx-auto mt-16 max-w-3xl rounded-3xl border bg-muted/40 p-8 text-center md:p-12"
          >
            <h2 className="text-2xl font-semibold tracking-tight">
              {escalation.title}
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              {escalation.description}
            </p>
            <div className="mt-6 flex justify-center">
              <Button asChild>
                <a href={mailtoHref}>
                  <Mail aria-hidden /> {supportCopy.escalationEmail}
                </a>
              </Button>
            </div>
          </section>
        </RevealScope>
      </Container>

      {/* Floating support chat — scoped to this page. */}
      <SupportChat />
    </>
  );
}
