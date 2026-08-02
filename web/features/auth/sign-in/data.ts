/** Sign-in screen copy. */
export const signInCopy = {
  title: "Welcome back",
  description: "Sign in to your Guardrail Hub workspace.",
  enterprise: {
    title: "Enterprise sign-in",
    description:
      "Use your organization's identity provider. We'll redirect you to complete sign-in.",
    note: "Single sign-on via OIDC or SAML 2.0, configured by your workspace admin.",
  },
  footer: {
    prompt: "Don't have an account?",
    linkLabel: "Create one",
  },
} as const;
