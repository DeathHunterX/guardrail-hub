import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import { Card, CardContent } from "@/components/ui/card";

import { channels, contactCopy, responseNote } from "./data";

export function Contact() {
  return (
    <>
      <PageHeader
        eyebrow={contactCopy.eyebrow}
        title={contactCopy.title}
        lede={contactCopy.lede}
      />

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {channels.map((channel) => {
              const isInternal =
                channel.action.href.startsWith("/") && !channel.action.external;

              return (
                <Card
                  data-reveal
                  key={channel.title}
                  className="flex flex-col bg-card/60 transition-colors hover:border-primary/40"
                >
                  <CardContent className="flex flex-1 flex-col p-6">
                    <channel.icon className="size-6 text-primary" aria-hidden />
                    <h2 className="mt-4 text-sm font-semibold">
                      {channel.title}
                    </h2>
                    <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                      {channel.description}
                    </p>
                    <p className="mt-5">
                      {isInternal ? (
                        <Link
                          href={channel.action.href}
                          className="group inline-flex items-center gap-1 text-sm font-medium text-primary"
                        >
                          {channel.action.label}
                          <ArrowUpRight
                            className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
                            aria-hidden
                          />
                        </Link>
                      ) : (
                        <a
                          href={channel.action.href}
                          target={channel.action.external ? "_blank" : undefined}
                          rel={channel.action.external ? "noreferrer" : undefined}
                          className="group inline-flex items-center gap-1 text-sm font-medium text-primary"
                        >
                          {channel.action.label}
                          <ArrowUpRight
                            className="size-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
                            aria-hidden
                          />
                        </a>
                      )}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <p
            data-reveal
            className="mx-auto mt-12 max-w-2xl text-center text-sm leading-relaxed text-muted-foreground"
          >
            {responseNote}
          </p>
        </RevealScope>
      </Container>
    </>
  );
}
