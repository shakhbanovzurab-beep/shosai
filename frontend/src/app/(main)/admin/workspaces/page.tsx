import type { Metadata } from "next";

import { WorkspacesScreen } from "@/features/admin-workspaces";

export const metadata: Metadata = {
  title: "Пространства",
  description: "Рабочие пространства команд: места, оплата, активность и доступ.",
  alternates: { canonical: "/admin/workspaces" },
};

export default function Page() {
  return <WorkspacesScreen />;
}
