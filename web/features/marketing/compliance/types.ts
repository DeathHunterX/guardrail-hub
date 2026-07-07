export interface ControlRow {
  control: string;
  evidence: string;
  status: "passing" | "attention";
  validated: string;
}
