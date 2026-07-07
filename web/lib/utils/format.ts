const compactFormatter = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});

/** Formats 24300 as "24.3K" — GitHub stars, stat chips. */
export function formatCompactNumber(value: number): string {
  return compactFormatter.format(value);
}
