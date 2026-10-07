import type { Metadata } from "next";

import { RolesScreen } from "@/features/admin-roles";

export const metadata: Metadata = {
  title: "Роли",
  description: "Просмотр уровней доступа и управление ролями и правами в организации.",
  alternates: {
    canonical: "/admin/roles",
  },
};

export default function Page() {
  return <RolesScreen />;
}
