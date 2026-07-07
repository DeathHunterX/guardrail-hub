import type { LucideIcon } from "lucide-react";

export interface SupportFaq {
  question: string;
  answer: string;
}

export interface SupportTopic {
  id: string;
  icon: LucideIcon;
  title: string;
  description: string;
  faqs: SupportFaq[];
}
