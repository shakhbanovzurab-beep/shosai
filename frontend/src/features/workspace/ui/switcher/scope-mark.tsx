"use client";

import { useWorkspaces } from "../../model/resources";
import { PersonalTile, WorkspaceTile } from "./workspace-tile";

/** The current context's mark alone, for the collapsed icon rail. */
export function ScopeMark({ slug }: { slug: string | null }) {
  const workspaces = useWorkspaces();
  const name =
    slug && workspaces.status === "ready" ? workspaces.data.workspaces.find((w) => w.slug === slug)?.name : undefined;
  return name ? <WorkspaceTile name={name} /> : <PersonalTile />;
}
