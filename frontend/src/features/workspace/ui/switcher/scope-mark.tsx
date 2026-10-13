"use client";

import { useWorkspaces } from "../../model/resources";
import { PersonalTile, WorkspaceTile } from "./workspace-tile";

/** The current context's mark alone, for the collapsed icon rail. */
export function ScopeMark({ slug }: { slug: string | null }) {
  const workspaces = useWorkspaces();
  const name =
    slug && workspaces.status === "ready" ? workspaces.data.workspaces.find((w) => w.slug === slug)?.name : undefined;
  // Знак шире поля кнопки рельса (16 px), почти во всю кнопку: отрицательный отступ держит его в центре.
  return name ? <WorkspaceTile name={name} /> : <PersonalTile className="-m-1.5 size-7!" />;
}
