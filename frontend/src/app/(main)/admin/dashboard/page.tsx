import type { Metadata } from "next";

import { DashboardScreen, parseDashboardTab } from "@/features/admin-dashboard";

export const metadata: Metadata = {
  title: "Дашборд",
  alternates: { canonical: "/admin/dashboard" },
};

interface PageProps {
  searchParams: Promise<{ tab?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { tab } = await searchParams;

  return <DashboardScreen tab={parseDashboardTab(tab)} />;
}
