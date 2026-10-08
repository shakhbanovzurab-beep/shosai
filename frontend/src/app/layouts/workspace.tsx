import { Outlet } from "react-router";

import { WorkspaceGate } from "@/features/workspace/ui/shared/workspace-gate";
import { useParams } from "@/lib/navigation";

/** Каждая страница пространства (/app/w/:workspace/…) открывается через его шлюз: членство и загрузка. */
export function Component() {
  const { workspace = "" } = useParams<{ workspace: string }>();
  return (
    <WorkspaceGate slug={workspace}>
      <Outlet />
    </WorkspaceGate>
  );
}
