/**
 * First focusable element on every page. Visually hidden until focused,
 * then floats above the sticky header.
 */
export function SkipLink() {
  return (
    <a
      href="#content"
      className="sr-only z-[60] rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus-visible:not-sr-only focus-visible:fixed focus-visible:left-4 focus-visible:top-4"
    >
      Skip to content
    </a>
  );
}
