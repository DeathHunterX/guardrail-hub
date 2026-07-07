export interface BlogPost {
  title: string;
  excerpt: string;
  /** Human-readable planned publication date. */
  date: string;
  readingTime: string;
  tag: "Engineering" | "Security" | "Product" | "Company";
  author: { name: string; role: string };
  featured?: boolean;
}
