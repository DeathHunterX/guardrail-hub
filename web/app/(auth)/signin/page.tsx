import type { Metadata } from "next";

import { SignIn } from "@/features/auth/sign-in";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your Guardrail Hub workspace.",
};

export default function SignInPage() {
  return <SignIn />;
}
