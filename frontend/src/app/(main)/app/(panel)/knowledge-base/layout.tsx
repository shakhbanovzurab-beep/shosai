import type { ReactNode } from "react";

import { FeatureGate } from "@/features/upgrade";

export default function Layout({ children }: Readonly<{ children: ReactNode }>) {
  return <FeatureGate feature="knowledge_base">{children}</FeatureGate>;
}
