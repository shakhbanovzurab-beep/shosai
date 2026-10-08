"use client";

import { useHubFromPath } from "@/features/hub/model/current-hub";
import { HubSignal } from "@/features/hub/ui/meeting/hub-signal";
import { LeoWidget } from "@/features/leo/ui/leo-widget";
import { workspaceSlugFromPath } from "@/features/workspace/domain/paths";
import { useWorkspaces } from "@/features/workspace/model/resources";
import { usePathname } from "@/lib/navigation";

/**
 * Leo in the user panel: inside a workspace it works in that workspace; on a hub's page only within
 * that hub (and it may open with the hub's one signal); everywhere else in Personal.
 */
export function UserPanelLeo() {
  const pathname = usePathname();
  const workspaces = useWorkspaces();
  const hub = useHubFromPath(pathname);
  const slug = workspaceSlugFromPath(pathname);
  const current =
    slug && workspaces.status === "ready" ? workspaces.data.workspaces.find((w) => w.slug === slug) : undefined;
  if (hub)
    return <LeoWidget context={{ kind: "hub", id: hub.id, name: hub.name }} notice={<HubSignal hubId={hub.id} />} />;
  return <LeoWidget context={current ? { kind: "workspace", id: current.id, name: current.name } : undefined} />;
}
