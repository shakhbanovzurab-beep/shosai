import {
  BookOpen,
  BrainCircuit,
  Calendar,
  Download,
  FolderKanban,
  FolderOpen,
  Gavel,
  House,
  Kanban,
  LayoutGrid,
  ListChecks,
  ListTodo,
  type LucideIcon,
  Mail,
  NotebookPen,
  Settings2,
  Users,
  Video,
} from "lucide-react";
import type { useTranslations } from "use-intl";

import { workspacePath } from "@/features/workspace/domain/paths";

/** The shell's translator, for building labelled navigation outside a component. */
export type ShellT = ReturnType<typeof useTranslations<"shell">>;

export type NavBadge = "new" | "soon";

export interface NavSubItem {
  id: string;
  title: string;
  url: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

interface NavItemBase {
  id: string;
  title: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

export interface NavMainLinkItem extends NavItemBase {
  url: string;
  subItems?: never;
}

export interface NavMainParentItem extends NavItemBase {
  subItems: NavSubItem[];
}

export type NavMainItem = NavMainLinkItem | NavMainParentItem;

export interface NavGroup {
  id: number;
  label?: string;
  items: NavMainItem[];
}

/** In the user menu, after Support, rather than in the list; still reachable from search. */
export const downloadAppItem = (t: ShellT): NavMainLinkItem => ({
  id: "download",
  title: t("nav.downloadApp"),
  url: "/app/download",
  icon: Download,
});

/** The user panel's sidebar, worded in the interface language. */
export function userPanelItems(t: ShellT): NavGroup[] {
  return [
    {
      id: 1,
      items: [
        { id: "productivity", title: t("nav.productivity"), url: "/app/productivity", icon: ListTodo },
        { id: "hub", title: t("nav.hub"), url: "/app/hub", icon: LayoutGrid },
      ],
    },
    {
      id: 2,
      items: [
        { id: "email", title: t("nav.email"), url: "/app/mail", icon: Mail },
        { id: "meetings", title: t("nav.meetings"), url: "/app/meetings", icon: Video },
        { id: "calendar", title: t("nav.calendar"), url: "/app/calendar", icon: Calendar },
      ],
    },
    {
      id: 3,
      items: [
        { id: "kanban", title: t("nav.kanban"), url: "/app/kanban", icon: Kanban },
        { id: "notes", title: t("nav.notes"), url: "/app/notes", icon: NotebookPen },
        { id: "file-manager", title: t("nav.fileManager"), url: "/app/file-manager", icon: FolderOpen },
      ],
    },
    {
      id: 4,
      items: [
        { id: "studio", title: t("nav.studio"), url: "/app/studio", icon: BrainCircuit },
        { id: "knowledge-base", title: t("nav.knowledge"), url: "/app/knowledge-base", icon: BookOpen },
      ],
    },
  ];
}

/**
 * A workspace's sidebar: the shared work first (projects, tasks, meetings, decisions, knowledge), then
 * the workspace itself. Personal tools stay in Personal, one choice away in the switcher and in search.
 */
export function workspaceSidebarItems(slug: string, t: ShellT): NavGroup[] {
  const url = (path = "") => workspacePath(slug, path);
  return [
    {
      id: 1,
      items: [
        { id: "ws-home", title: t("workspaceNav.home"), url: url(), icon: House },
        { id: "ws-projects", title: t("workspaceNav.projects"), url: url("/projects"), icon: FolderKanban },
        { id: "ws-tasks", title: t("workspaceNav.tasks"), url: url("/tasks"), icon: ListChecks },
        { id: "ws-meetings", title: t("workspaceNav.meetings"), url: url("/meetings"), icon: Video },
        { id: "ws-decisions", title: t("workspaceNav.decisions"), url: url("/decisions"), icon: Gavel },
        { id: "ws-knowledge", title: t("workspaceNav.knowledge"), url: url("/knowledge"), icon: BookOpen },
      ],
    },
    {
      id: 2,
      label: t("workspaceNav.group"),
      items: [
        { id: "ws-members", title: t("workspaceNav.members"), url: url("/members"), icon: Users },
        { id: "ws-settings", title: t("workspaceNav.settings"), url: url("/settings"), icon: Settings2 },
      ],
    },
  ];
}
