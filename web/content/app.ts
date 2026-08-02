import {
  Bell,
  Blocks,
  FileText,
  Gauge,
  GlobeLock,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  Link2,
  FolderGit2,
  Package,
  Palette,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  Workflow,
} from "lucide-react";

import type { AppNavSection, SettingsNavGroup } from "@/types/navigation";

/**
 * Authenticated app-shell navigation (chrome-level data, mirroring
 * content/site.ts for the marketing chrome). Modules marked `planned` have no
 * backend yet — their routes render the shared module-placeholder state.
 */
export const appNavigation: AppNavSection[] = [
  {
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "Projects", href: "/projects", icon: FolderGit2, planned: true },
      {
        label: "Operations",
        href: "/operations",
        icon: Workflow,
        planned: true,
      },
      {
        label: "Security",
        href: "/security-center",
        icon: ShieldCheck,
        planned: true,
      },
      {
        label: "Performance",
        href: "/performance",
        icon: Gauge,
        planned: true,
      },
      { label: "Reports", href: "/reports", icon: FileText, planned: true },
      { label: "Artifacts", href: "/artifacts", icon: Package, planned: true },
      // "/security" and "/support" belong to marketing pages; app modules use
      // distinct paths since route groups share one URL space.
      {
        label: "Integrations",
        href: "/integrations",
        icon: Blocks,
        planned: true,
      },
    ],
  },
  {
    label: "General",
    items: [
      { label: "Settings", href: "/settings/profile", icon: Settings },
      { label: "Help", href: "/help", icon: LifeBuoy, planned: true },
    ],
  },
];

export const settingsNavigation: SettingsNavGroup[] = [
  {
    label: "Account",
    items: [
      { label: "Profile", href: "/settings/profile", icon: UserRound },
      { label: "Security", href: "/settings/security", icon: KeyRound },
      {
        label: "Connected accounts",
        href: "/settings/connected-accounts",
        icon: Link2,
      },
      {
        label: "Enterprise identity",
        href: "/settings/enterprise",
        icon: GlobeLock,
      },
    ],
  },
  {
    label: "Application",
    items: [
      { label: "General", href: "/settings/general", icon: SlidersHorizontal },
      { label: "Appearance", href: "/settings/appearance", icon: Palette },
      { label: "Notifications", href: "/settings/notifications", icon: Bell },
    ],
  },
];
