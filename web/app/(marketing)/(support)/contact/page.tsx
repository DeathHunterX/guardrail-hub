import type { Metadata } from "next";

import { Contact } from "@/features/support/contact";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Reach the Guardrail Hub team — sales and demos, support, security reports, community, and press.",
};

export default function ContactPage() {
  return <Contact />;
}
