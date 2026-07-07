import { Github, MessageCircle } from "lucide-react";

import { Container } from "@/components/common/container";
import { PageHeader } from "@/components/common/page-header";
import { RevealScope } from "@/components/effects/reveal-scope";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { externalLinks } from "@/constants/external-links";

import { blogCopy, blogCta, posts } from "./data";

const tagVariant = {
  Engineering: "secondary",
  Security: "warning",
  Product: "success",
  Company: "outline",
} as const;

/** Author line shared by the featured card and grid cards. */
function AuthorLine({
  author,
  readingTime,
}: {
  author: { name: string; role: string };
  readingTime: string;
}) {
  return (
    <p className="text-xs text-muted-foreground">
      <span className="font-medium text-foreground">{author.name}</span>
      {" · "}
      {author.role}
      {" · "}
      {readingTime}
    </p>
  );
}

export function Blog() {
  // Fall back to the first post when nothing is flagged as featured.
  const [firstPost] = posts;
  const featured = posts.find((post) => post.featured) ?? firstPost;
  if (!featured) return null;
  const rest = posts.filter((post) => post !== featured);

  return (
    <>
      <PageHeader
        eyebrow={blogCopy.eyebrow}
        title={blogCopy.title}
        lede={blogCopy.lede}
      />

      <Container className="pb-20 md:pb-28">
        <RevealScope>
          {/* Featured (upcoming) post. */}
          <Card data-reveal className="overflow-hidden bg-card/60">
            <CardContent className="grid gap-8 p-8 md:grid-cols-[1fr_auto] md:items-end md:p-10">
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant={tagVariant[featured.tag]}>{featured.tag}</Badge>
                  <span className="text-xs text-muted-foreground">
                    {featured.date}
                  </span>
                </div>
                <h2 className="mt-4 text-balance text-2xl font-semibold tracking-tight md:text-3xl">
                  {featured.title}
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                  {featured.excerpt}
                </p>
              </div>
              <AuthorLine
                author={featured.author}
                readingTime={featured.readingTime}
              />
            </CardContent>
          </Card>

          {/* Upcoming posts grid. */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {rest.map((post) => (
              <Card data-reveal key={post.title} className="flex flex-col bg-card/60">
                <CardContent className="flex flex-1 flex-col p-6">
                  <div className="flex items-center gap-2">
                    <Badge variant={tagVariant[post.tag]}>{post.tag}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {post.date}
                    </span>
                  </div>
                  <h3 className="mt-4 text-balance text-base font-semibold leading-snug">
                    {post.title}
                  </h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                    {post.excerpt}
                  </p>
                  <div className="mt-5 border-t pt-4">
                    <AuthorLine
                      author={post.author}
                      readingTime={post.readingTime}
                    />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Follow CTA — posts publish at launch, so point at the channels. */}
          <section
            data-reveal
            aria-label={blogCta.title}
            className="mx-auto mt-16 max-w-3xl rounded-3xl border bg-muted/40 p-8 text-center md:p-12"
          >
            <h2 className="text-2xl font-semibold tracking-tight">
              {blogCta.title}
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
              {blogCta.description}
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button asChild>
                <a href={externalLinks.github} target="_blank" rel="noreferrer">
                  <Github aria-hidden /> Follow on GitHub
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href={externalLinks.discord} target="_blank" rel="noreferrer">
                  <MessageCircle aria-hidden /> Join the Discord
                </a>
              </Button>
            </div>
          </section>
        </RevealScope>
      </Container>
    </>
  );
}
