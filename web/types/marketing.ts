export interface Tier {
  id: string;
  name: string;
  monthly: number | null;
  positioning: string;
  features: string[];
  cta: { label: string; href: string };
  featured?: boolean;
}

export interface Testimonial {
  quote: string;
  name: string;
  role: string;
  company: string;
  metric?: string;
}
