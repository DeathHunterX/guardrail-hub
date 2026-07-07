import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";

export interface LegalSection {
  /** Anchor id — also used by the table of contents. */
  id: string;
  heading: string;
  paragraphs: string[];
  /** Optional bullet list rendered after the paragraphs. */
  items?: string[];
}

export interface LegalDoc {
  eyebrow: string;
  title: string;
  lede: string;
  /** Human-readable "Last updated" date. */
  updated: string;
  sections: LegalSection[];
}

/**
 * Document-style page layout shared by Privacy, Terms, and the DPA:
 * left-aligned header, sticky table of contents on desktop, and a
 * numbered section flow with anchor targets.
 */
export function LegalArticle({ doc }: { doc: LegalDoc }) {
  return (
    <>
      <PageHeader
        eyebrow={doc.eyebrow}
        title={doc.title}
        lede={doc.lede}
        align="left"
      >
        <p data-reveal className="mt-4 text-sm text-muted-foreground">
          Last updated: <time>{doc.updated}</time>
        </p>
      </PageHeader>

      <Container className="pb-20 md:pb-28">
        <div className="grid gap-12 lg:grid-cols-[240px_minmax(0,1fr)]">
          {/* Sticky table of contents — desktop only. */}
          <nav
            aria-label="Table of contents"
            className="hidden self-start lg:sticky lg:top-24 lg:block"
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              On this page
            </p>
            <ol className="mt-4 space-y-2.5 text-sm">
              {doc.sections.map((section, index) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className="inline-flex gap-2 text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <span className="font-mono text-xs leading-5 text-muted-foreground/60">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {section.heading}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <article className="max-w-3xl">
            {doc.sections.map((section, index) => (
              <section
                key={section.id}
                id={section.id}
                aria-labelledby={`${section.id}-heading`}
                className="scroll-mt-24 border-b py-8 first:pt-0 last:border-b-0"
              >
                <h2
                  id={`${section.id}-heading`}
                  className="flex items-baseline gap-3 text-xl font-semibold tracking-tight"
                >
                  <span className="font-mono text-sm text-muted-foreground/60">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {section.heading}
                </h2>
                <div className="mt-4 space-y-4 text-[0.9375rem] leading-relaxed text-muted-foreground">
                  {section.paragraphs.map((paragraph) => (
                    <p key={paragraph.slice(0, 48)}>{paragraph}</p>
                  ))}
                  {section.items ? (
                    <ul className="list-disc space-y-2 pl-5">
                      {section.items.map((item) => (
                        <li key={item.slice(0, 48)}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </section>
            ))}
          </article>
        </div>
      </Container>
    </>
  );
}
