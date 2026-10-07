import type { Metadata } from "next";

import { WorkspaceScreen } from "@/features/admin-workspaces";

export const metadata: Metadata = {
  title: "Пространство",
};

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function Page({ params }: PageProps) {
  const { id } = await params;
  return <WorkspaceScreen id={decodeURIComponent(id)} />;
}
