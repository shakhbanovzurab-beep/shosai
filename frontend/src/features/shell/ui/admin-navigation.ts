import {
  Bug,
  Building2,
  Cpu,
  LayoutDashboard,
  LifeBuoy,
  Lock,
  MonitorDown,
  ScrollText,
  TicketPercent,
  UserRound,
  Users,
  Video,
  Wallet,
} from "lucide-react";

import type { NavGroup } from "./navigation";

/** The admin panel's sidebar. The admin panel is written in Russian only, so its labels live here, not in the catalogs. */
export const adminSidebarItems: NavGroup[] = [
  {
    id: 1,
    items: [{ id: "admin-dashboard", title: "Дашборд", url: "/admin/dashboard", icon: LayoutDashboard }],
  },
  {
    id: 2,
    label: "Пользователи и доступ",
    items: [
      { id: "users", title: "Пользователи", url: "/admin/users", icon: Users },
      { id: "workspaces", title: "Пространства", url: "/admin/workspaces", icon: Building2 },
      { id: "roles", title: "Роли", url: "/admin/roles", icon: Lock },
    ],
  },
  {
    id: 3,
    label: "Монетизация",
    items: [
      { id: "plans", title: "Тарифы и промокоды", url: "/admin/plans", icon: TicketPercent },
      { id: "billing", title: "Финансы и биллинг", url: "/admin/billing", icon: Wallet },
    ],
  },
  {
    id: 4,
    label: "Платформа",
    items: [
      { id: "ai-models", title: "AI-модели", url: "/admin/ai-models", icon: Cpu },
      { id: "platform-prompts", title: "Промты платформы", url: "/admin/platform-prompts", icon: ScrollText },
      { id: "livekit", title: "LiveKit", url: "/admin/livekit", icon: Video },
      { id: "apps", title: "Приложения", url: "/admin/apps", icon: MonitorDown },
    ],
  },
  {
    id: 5,
    label: "Сопровождение",
    items: [
      { id: "errors", title: "Ошибки", url: "/admin/errors", icon: Bug },
      { id: "support", title: "Поддержка", url: "/admin/support", icon: LifeBuoy },
    ],
  },
  {
    id: 6,
    label: "Аккаунт",
    items: [{ id: "profile", title: "Профиль", url: "/admin/profile", icon: UserRound }],
  },
];
