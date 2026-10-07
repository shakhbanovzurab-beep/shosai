"use client";

import { createContext, use } from "react";

/** The workspace the current page belongs to, set by the gate around the Workspace pages. */
export const WorkspaceContext = createContext<{ id: string; slug: string } | null>(null);

export function useWorkspaceRef() {
  const ref = use(WorkspaceContext);
  if (!ref) throw new Error("useWorkspaceRef must be used inside WorkspaceGate.");
  return ref;
}
