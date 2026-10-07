import type { Metadata } from "next";

import { BillingScreen } from "@/features/admin-billing";

export const metadata: Metadata = {
  title: "Финансы и биллинг",
  alternates: { canonical: "/admin/billing" },
};

export default function Page() {
  return <BillingScreen />;
}
