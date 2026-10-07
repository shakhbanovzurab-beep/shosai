import type { Metadata } from "next";

import { SupportScreen } from "@/features/admin-support";

export const metadata: Metadata = {
  title: "Поддержка",
  alternates: {
    canonical: "/admin/support",
  },
};

interface PageProps {
  searchParams: Promise<{ ticket?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  // `?ticket=<conversation id>` opens that conversation, e.g. from an issue on the errors page.
  const { ticket } = await searchParams;
  return <SupportScreen initialTicket={typeof ticket === "string" ? ticket : null} />;
}
