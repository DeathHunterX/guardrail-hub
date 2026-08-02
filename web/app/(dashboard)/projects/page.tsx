import type { Metadata } from "next";

import { ModulePlaceholder } from "@/features/dashboard/module-placeholder";

export const metadata: Metadata = {
  title: "Projects",
};

export default function ProjectsPage() {
  return <ModulePlaceholder module="projects" />;
}
