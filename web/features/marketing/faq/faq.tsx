import { ArrowUpRight } from "lucide-react";

import { Container } from "@/components/common/container";
import { RevealScope } from "@/components/effects/reveal-scope";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { siteConfig } from "@/config/site";
import { externalLinks } from "@/constants/external-links";

import { faqCopy, faqItems } from "./data";

/** FAQPage structured data for search engines. */
function FaqJsonLd() {
  const json = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqItems.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(json) }}
    />
  );
}

/**
 * FAQ (spec §14): sticky header column + single-open accordion. Minimal
 * motion by design — FAQs are for reading.
 */
export function FAQ() {
  return (
    <section id="faq" aria-labelledby="faq-heading" className="py-12 md:py-14">
      <FaqJsonLd />
      <Container>
        <RevealScope className="grid gap-12 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <div className="lg:sticky lg:top-24">
              <p
                data-reveal
                className="text-[0.8125rem] font-medium uppercase tracking-widest text-muted-foreground"
              >
                {faqCopy.eyebrow}
              </p>
              <h2
                data-reveal
                id="faq-heading"
                className="mt-3 text-balance text-heading-2"
              >
                {faqCopy.title}
              </h2>
              <p data-reveal className="mt-4 text-sm text-muted-foreground">
                Still curious?{" "}
                <a
                  href={externalLinks.docs}
                  target="_blank"
                  rel="noreferrer"
                  className="group inline-flex items-center gap-0.5 font-medium text-primary"
                >
                  Read the docs
                  <ArrowUpRight className="size-3.5" aria-hidden />
                </a>{" "}
                or{" "}
                <a
                  href={siteConfig.app.bookDemo}
                  className="font-medium text-primary"
                >
                  talk to us
                </a>
                .
              </p>
            </div>
          </div>
          <div data-reveal className="lg:col-span-8">
            <Accordion type="single" collapsible className="w-full">
              {faqItems.map((item) => (
                <AccordionItem key={item.id} value={item.id} id={`faq-${item.id}`}>
                  <AccordionTrigger className="py-5 text-base">
                    {item.question}
                  </AccordionTrigger>
                  <AccordionContent className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                    {item.answer}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </RevealScope>
      </Container>
    </section>
  );
}
