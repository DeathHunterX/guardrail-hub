export interface Integration {
  name: string;
  description: string;
  category: "scanners" | "testing" | "cicd" | "workflow" | "cloud";
  /** Inner-ring items orbit closest to the hub. */
  ring?: "inner" | "outer";
}
