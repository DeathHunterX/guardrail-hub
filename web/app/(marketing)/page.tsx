import {
  Agent,
  Compliance,
  FAQ,
  Features,
  FinalCTA,
  Hero,
  Integrations,
  Pricing,
  Problem,
  Showcase,
  Testimonials,
  TrustedBy,
  Workflow,
} from "@/components/sections";

/**
 * Home page — the narrative order is the spec's eight-act arc:
 * hook -> trust seed -> tension -> resolution -> differentiation ->
 * assurance -> decision -> commitment.
 */
export default function HomePage() {
  return (
    <>
      <Hero />
      <TrustedBy />
      <Problem />
      <Workflow />
      <Features />
      <Showcase />
      <Agent />
      <Integrations />
      <Compliance />
      <Testimonials />
      <Pricing />
      <FAQ />
      <FinalCTA />
    </>
  );
}
