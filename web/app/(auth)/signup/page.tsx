import type { Metadata } from "next";

import { SignUp } from "@/features/auth/sign-up";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create your Guardrail Hub account.",
};

export default function SignUpPage() {
  return <SignUp />;
}
