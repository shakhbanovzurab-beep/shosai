import type { ReactNode } from "react";

import { WorkspaceGate } from "@/features/workspace";

interface LayoutProps {
  children: ReactNode;
  params: Promise<{ workspace: string }>;
}

export default async function Layout({ children, params }: LayoutProps) {
  const { workspace } = await params;
  return <WorkspaceGate slug={decodeURIComponent(workspace)}>{children}</WorkspaceGate>;
}
