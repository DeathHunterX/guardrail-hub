import { externalLinks } from "@/constants/external-links";

interface GitHubRepoResponse {
  stargazers_count: number;
}

/**
 * Fetches the star count at build time, revalidated hourly (ISR) — the page
 * itself stays fully static. Any failure degrades to a plain GitHub link.
 */
export async function getGitHubStars(): Promise<number | null> {
  try {
    const response = await fetch(
      `https://api.github.com/repos/${externalLinks.githubRepo}`,
      {
        headers: { Accept: "application/vnd.github+json" },
        next: { revalidate: 3600 },
      },
    );
    if (!response.ok) return null;
    const data = (await response.json()) as GitHubRepoResponse;
    return data.stargazers_count;
  } catch {
    return null;
  }
}
