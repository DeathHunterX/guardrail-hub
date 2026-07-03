import { Container } from "@/components/shared/container";

import { HeroCopy } from "./hero-copy";
import { HeroWorkspace } from "./hero-workspace";

/**
 * Hero (spec §3): copy beside the live AI workspace, over an ambient
 * gradient mesh. The single h1 of the page lives here.
 */
export function Hero() {
  return (
    <section id="hero" aria-label="Introduction" className="relative isolate overflow-hidden">
      {/* Ambient gradient mesh — decorative, token-driven, theme-adaptive. */}
      <div aria-hidden="true" className="absolute inset-0 -z-10">
        <div className="absolute -top-24 left-[8%] size-[28rem] rounded-full bg-gradient-to-br from-primary/20 via-primary/5 to-transparent blur-3xl [opacity:var(--glow-opacity)] dark:from-primary/40" />
        <div className="absolute right-[4%] top-1/3 size-[24rem] rounded-full bg-gradient-to-br from-highlight/20 via-highlight/5 to-transparent blur-3xl [opacity:var(--glow-opacity)] dark:from-highlight/40" />
      </div>
      <Container>
        <div className="grid items-center gap-14 pb-24 pt-16 md:pt-24 lg:grid-cols-12 lg:gap-8">
          <div className="lg:col-span-5">
            <HeroCopy />
          </div>
          <div className="lg:col-span-7">
            <HeroWorkspace />
          </div>
        </div>
      </Container>
    </section>
  );
}
