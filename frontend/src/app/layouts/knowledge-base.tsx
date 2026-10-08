import { Outlet } from "react-router";

import { FeatureGate } from "@/features/upgrade/ui/feature-gate";

export function Component() {
  return (
    <FeatureGate feature="knowledge_base">
      <Outlet />
    </FeatureGate>
  );
}
