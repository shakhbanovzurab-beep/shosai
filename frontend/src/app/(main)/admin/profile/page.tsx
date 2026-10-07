import type { Metadata } from "next";

import { ProfileScreen } from "@/features/admin-profile";

export const metadata: Metadata = {
  title: "Профиль",
  description: "Профиль сотрудника: личные данные, сведения о работе, отпуска, документы и линия подчинения.",
  alternates: {
    canonical: "/admin/profile",
  },
};

export default function Page() {
  return <ProfileScreen />;
}
