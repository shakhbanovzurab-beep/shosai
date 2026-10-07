import type { Metadata } from "next";

import { PlansScreen } from "@/features/admin-plans";

export const metadata: Metadata = {
  title: "Тарифы и промокоды",
  description: "Управление тарифами Leo, их ценами и лимитами, а также промокодами.",
};

export default function Page() {
  return <PlansScreen />;
}
