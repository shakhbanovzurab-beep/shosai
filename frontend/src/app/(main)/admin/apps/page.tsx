import type { Metadata } from "next";

import { AppsScreen } from "@/features/admin-apps";

export const metadata: Metadata = {
  title: "Приложения",
  description: "Сборки Leo для macOS и Windows: загрузка, публикация и поэтапная раскатка.",
  alternates: {
    canonical: "/admin/apps",
  },
};

export default function Page() {
  return <AppsScreen />;
}
