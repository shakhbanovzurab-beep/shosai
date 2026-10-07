import type { Metadata } from "next";

import { UsersScreen } from "@/features/admin-users";

export const metadata: Metadata = {
  title: "Пользователи",
  description: "Просмотр, фильтрация и управление учётными записями пользователей.",
  alternates: {
    canonical: "/admin/users",
  },
};

export default function Page() {
  return <UsersScreen />;
}
