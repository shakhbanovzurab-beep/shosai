import type { Metadata } from "next";

import { ErrorsScreen } from "@/features/admin-errors";

export const metadata: Metadata = {
  title: "Ошибки",
  description: "Ошибки платформы Leo и десктоп-клиентов для macOS и Windows, сгруппированные по причине.",
  alternates: { canonical: "/admin/errors" },
};

export default function Page() {
  return <ErrorsScreen />;
}
