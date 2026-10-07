import type { ReactNode } from "react";

import { PanelLayout } from "@/features/shell";

export default function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return <PanelLayout panel="dashboard">{children}</PanelLayout>;
}
