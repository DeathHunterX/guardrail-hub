export type UpdateKind = "New" | "Improved" | "Fixed";

export interface ReleaseUpdate {
  kind: UpdateKind;
  text: string;
}

export interface Release {
  version: string;
  /** Human-readable release date. */
  date: string;
  /** Product maturity stage shown as a chip next to the version. */
  stage: "In development";
  title: string;
  /** Short overview of the release — the "why", not the diff. */
  overview: string;
  /** The headline updates; the full list lives in the GitHub release notes. */
  highlights: ReleaseUpdate[];
  /** Link to the full release notes. */
  detailUrl: string;
  latest?: boolean;
}
