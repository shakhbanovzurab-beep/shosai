"use client";

import { usePathname } from "next/navigation";

import { HubSignal, useHubFromPath } from "@/features/hub";
import { LeoWidget } from "@/features/leo";
import { useWorkspaces, workspaceSlugFromPath } from "@/features/workspace";

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
