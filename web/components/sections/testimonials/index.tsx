import { Quote } from "lucide-react";

import { Marquee } from "@/components/shared/marquee";
import { SectionShell } from "@/components/shared/section-shell";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

import {
  featured,
  testimonials,
  testimonialsCopy,
  type Testimonial,
} from "./testimonials.data";

function initialsOf(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2);
}

function TestimonialCard({ testimonial }: { testimonial: Testimonial }) {
  return (
    <figure className="mx-3 flex w-[340px] shrink-0 flex-col rounded-2xl border bg-card p-6">
      <blockquote className="text-sm leading-relaxed text-muted-foreground">
        “{testimonial.quote}”
      </blockquote>
      <figcaption className="mt-4 flex items-center gap-3">
        <Avatar className="size-8">
          <AvatarFallback>{initialsOf(testimonial.name)}</AvatarFallback>
        </Avatar>
        <span className="min-w-0 text-xs">
          <cite className="block truncate font-medium not-italic text-foreground">
            {testimonial.name}
          </cite>
          <span className="block truncate text-muted-foreground">
            {testimonial.role} · {testimonial.company}
          </span>
        </span>
        {testimonial.metric ? (
          <Badge variant="success" className="ml-auto shrink-0 text-[10px]">
            {testimonial.metric}
          </Badge>
        ) : null}
      </figcaption>
    </figure>
  );
}

/**
 * Testimonials (spec §12): anchor quote + two counter-scrolling marquee rows.
 * Row durations are mismatched on purpose — no visible sync pattern.
 */
export function Testimonials() {
  const firstRow = testimonials.slice(0, 3);
  const secondRow = testimonials.slice(3);

  return (
    <SectionShell
      id="testimonials"
      eyebrow={testimonialsCopy.eyebrow}
      title={testimonialsCopy.title}
    >
      <figure
        data-reveal
        className="relative mx-auto max-w-3xl rounded-3xl border bg-card p-8 md:p-10"
      >
        <Quote
          aria-hidden="true"
          className="absolute -top-4 left-8 size-8 rotate-180 text-primary/20"
        />
        <blockquote className="text-pretty text-lg font-medium leading-relaxed md:text-xl">
          “{featured.quote}”
        </blockquote>
        <figcaption className="mt-6 flex items-center gap-3">
          <Avatar>
            <AvatarFallback>{initialsOf(featured.name)}</AvatarFallback>
          </Avatar>
          <span className="text-sm">
            <cite className="block font-semibold not-italic">{featured.name}</cite>
            <span className="text-muted-foreground">
              {featured.role}, {featured.company}
            </span>
          </span>
          {featured.metric ? (
            <Badge variant="success" className="ml-auto hidden sm:inline-flex">
              {featured.metric}
            </Badge>
          ) : null}
        </figcaption>
      </figure>

      <div data-reveal className="mt-10 space-y-6">
        <Marquee speed={55}>
          {firstRow.map((testimonial) => (
            <TestimonialCard key={testimonial.name} testimonial={testimonial} />
          ))}
        </Marquee>
        <Marquee speed={70} direction="right">
          {secondRow.map((testimonial) => (
            <TestimonialCard key={testimonial.name} testimonial={testimonial} />
          ))}
        </Marquee>
      </div>
    </SectionShell>
  );
}
