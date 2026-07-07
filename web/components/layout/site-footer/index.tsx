import { Github, Linkedin, MessageCircle, Twitter, Youtube } from "lucide-react";

import { Logo } from "@/components/layout/logo";
import { Container } from "@/components/common/container";
import { StatusDot } from "@/components/common/status-dot";
import { ThemeToggle } from "@/components/common/theme-toggle";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { externalLinks } from "@/constants/external-links";

import { FooterNavLink } from "./footer-nav-link";
import { footerGroups, footerTagline } from "./footer.data";

const socials = [
  { label: "GitHub", href: externalLinks.github, icon: Github },
  { label: "X (Twitter)", href: externalLinks.x, icon: Twitter },
  { label: "LinkedIn", href: externalLinks.linkedin, icon: Linkedin },
  { label: "Discord", href: externalLinks.discord, icon: MessageCircle },
  { label: "YouTube", href: externalLinks.youtube, icon: Youtube },
];

/** Footer (spec §16): sitemap, status, social, legal — dense but effortless. */
export function SiteFooter() {
  return (
    <footer className="relative overflow-hidden border-t bg-muted/30 py-12">
      {/* Watermark shield, cropped bottom-right. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={0.75}
        className="pointer-events-none absolute -bottom-24 -right-16 size-96 text-muted-foreground/10"
      >
        <path d="M12 3l7 3v5.5c0 4.4-2.9 8-7 9.5-4.1-1.5-7-5.1-7-9.5V6l7-3z" />
      </svg>
      <Container className="relative">
        <div className="grid gap-10 lg:grid-cols-6">
          <div className="lg:col-span-2">
            <Logo />
            <p className="mt-4 max-w-xs text-sm text-muted-foreground">
              {footerTagline}
            </p>
            <div className="mt-5 flex items-center gap-1">
              {socials.map((social) => (
                <Button
                  key={social.label}
                  asChild
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground"
                >
                  <a
                    href={social.href}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={social.label}
                  >
                    <social.icon aria-hidden />
                  </a>
                </Button>
              ))}
            </div>
            {/* Contact line closes the brand column — controls live in the
                bottom bar so this column stays short. */}
            <p className="mt-5 text-xs text-muted-foreground">
              Questions?{" "}
              <a
                href="mailto:hello@guardrailhub.com"
                className="font-medium text-foreground hover:text-primary"
              >
                hello@guardrailhub.com
              </a>
            </p>
          </div>

          <nav
            aria-label="Footer"
            className="grid grid-cols-2 gap-8 sm:grid-cols-4 lg:col-span-4"
          >
            {footerGroups.map((group) => (
              <div key={group.heading}>
                <h3 className="text-sm font-semibold">{group.heading}</h3>
                <ul className="mt-4 space-y-2.5 text-sm">
                  {group.links.map((link) => (
                    <li key={link.label}>
                      {link.external ? (
                        <a
                          href={link.href}
                          target="_blank"
                          rel="noreferrer"
                          className="text-muted-foreground transition-all hover:translate-x-0.5 hover:text-foreground motion-reduce:hover:translate-x-0 inline-block"
                        >
                          {link.label}
                        </a>
                      ) : (
                        <FooterNavLink link={link} />
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>

        <Separator className="my-8" />

        {/* Bottom bar hosts status + theme controls to keep the footer flat. */}
        <div className="flex flex-col items-center justify-between gap-5 text-xs text-muted-foreground lg:flex-row">
          <p>
            © {new Date().getFullYear()} Guardrail Hub, Inc. All rights
            reserved.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <a
              href={externalLinks.status}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full border bg-card/60 px-3 py-1.5 transition-colors hover:border-success/40 hover:text-foreground"
            >
              <StatusDot status="success" pulse />
              All systems operational
            </a>
            <ThemeToggle variant="segmented" />
          </div>
          <p className="flex items-center gap-3">
            <span>SOC 2 Type II</span>
            <span aria-hidden="true">·</span>
            <span>ISO 27001</span>
            <span aria-hidden="true">·</span>
            <span>GDPR</span>
          </p>
        </div>
      </Container>
    </footer>
  );
}
