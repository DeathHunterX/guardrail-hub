import { AnimatedNumber } from "@/components/effects/animated-number";
import { Container } from "@/components/common/container";
import { Marquee } from "@/components/effects/marquee";
import { RevealScope } from "@/components/effects/reveal-scope";

const customers = [
  "Vantel",
  "Nortcloud",
  "Kitewire",
  "Signalbay",
  "Oxbridge Systems",
  "Lumenard",
  "Parcelio",
  "Hexlane",
  "Drayven",
  "Corely",
];

const stats = [
  {
    value: 12_000_000,
    unit: "+",
    label: "scans run",
    style: "compact",
  },
  {
    value: 40_000,
    unit: "+",
    label: "vulnerabilities remediated",
    style: "compact",
  },
  {
    value: 99.9,
    unit: "%",
    label: "uptime, last 12 months",
    style: "one-decimal",
  },
] as const;

/**
 * Trusted By (spec §4): label framed by hairlines, a continuously scrolling
 * logo marquee, and a three-up stat band with big animated numbers. Kept
 * tight and close to the hero so it reads as its coda, not a stray section.
 */
export function TrustedBy() {
  return (
    <section aria-label="Customers" className="py-8 md:py-10">
      <Container>
        <RevealScope>
          {/* Quiet label framed by hairlines on both sides. */}
          <div data-reveal className="flex items-center gap-4">
            <span aria-hidden="true" className="h-px flex-1 bg-border" />
            <p className="shrink-0 text-sm text-muted-foreground">
              Trusted by security-minded engineering teams
            </p>
            <span aria-hidden="true" className="h-px flex-1 bg-border" />
          </div>

          {/* Infinite horizontal logo scroll. */}
          <div data-reveal className="mt-6" aria-label="Customer logos">
            <Marquee speed={40}>
              {customers.map((name) => (
                <span
                  key={name}
                  className="mx-8 whitespace-nowrap text-lg font-semibold tracking-tight text-muted-foreground/70 transition-colors hover:text-foreground"
                >
                  {name}
                </span>
              ))}
            </Marquee>
          </div>

          {/* Stat band: large numerals, dividers on desktop only. */}
          <dl
            data-reveal
            className="mt-8 grid gap-8 text-center sm:grid-cols-3 sm:gap-0 sm:divide-x sm:divide-border"
          >
            {stats.map((stat) => (
              <div key={stat.label} className="px-6">
                <dd className="font-mono text-3xl font-semibold tracking-tight text-foreground">
                  <AnimatedNumber value={stat.value} formatStyle={stat.style} />
                  {stat.unit}
                </dd>
                <dt className="mt-1.5 text-sm text-muted-foreground">
                  {stat.label}
                </dt>
              </div>
            ))}
          </dl>
        </RevealScope>
      </Container>
    </section>
  );
}
