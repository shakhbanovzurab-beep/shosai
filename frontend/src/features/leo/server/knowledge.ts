import { type LeoFiles, leoFiles } from "@/features/file-manager/server";
import { type LeoWorkspaceKnowledge, leoKnowledge, leoKnowledgeEverywhere } from "@/features/workspace/server";

import type { LeoRequest } from "../domain/request";

/*
 * What Leo may read for a request, decided before anything is planned. Personal: the account's own
 * files it chose for Leo, plus what every workspace lets it use as a member, each labeled with its
 * workspace. A workspace: only that workspace. A hub answers from the hub alone, so neither applies.
 */

export type KnowledgeScope =
  | { kind: "personal"; files: LeoFiles; workspaces: LeoWorkspaceKnowledge[] }
  | { kind: "workspace"; workspace: LeoWorkspaceKnowledge }
  | null;

export function knowledgeScope(request: LeoRequest): KnowledgeScope {
  const query = request.messages[request.messages.length - 1].content;
  const context = request.context ?? { kind: "personal" };
  if (context.kind === "hub") return null;
  if (context.kind === "workspace") {
    const workspace = leoKnowledge(context.workspace_id, query);
    return workspace ? { kind: "workspace", workspace } : null;
  }
  return { kind: "personal", files: leoFiles(query), workspaces: leoKnowledgeEverywhere(query) };
}

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;
const bold = (names: string[]) => names.map((name) => `**${name}**`).join(", ");

/** The knowledge step's line in the plan: what was searched, and what turned up. */
export function knowledgeStepText(scope: Exclude<KnowledgeScope, null>) {
  if (scope.kind === "workspace") {
    const { workspace, usable, matched, meetings } = scope.workspace;
    const found = [...matched.map((k) => k.name), ...meetings.map((m) => m.title)];
    return {
      detail: `${workspace.name} · ${plural(usable.length, "file")} and the meetings you can open`,
      result: found.length ? `Found ${found.join(", ")}` : "Nothing matched by name",
    };
  }
  const shared = scope.workspaces.reduce((sum, w) => sum + w.usable.length, 0);
  const found = [
    ...scope.files.matched.map((f) => f.name),
    ...scope.workspaces.flatMap((w) => w.matched.map((k) => `${k.name} (${w.workspace.name})`)),
  ];
  const where = scope.workspaces.length
    ? ` + ${plural(shared, "file")} from ${plural(scope.workspaces.length, "workspace")}`
    : "";
  return {
    detail: `Your ${plural(scope.files.usable.length, "file")}${where}`,
    result: found.length ? `Found ${found.join(", ")}` : "Nothing matched by name",
  };
}

/** What Leo can say about the knowledge it searched, and what it deliberately left out. */
export function knowledgeNote(scope: Exclude<KnowledgeScope, null>) {
  if (scope.kind === "workspace") {
    const { workspace, usable, matched, meetings, hidden } = scope.workspace;
    const name = workspace.name;
    const found = [...matched.map((k) => k.name), ...meetings.map((m) => m.title)];
    const lead = found.length
      ? `In **${name}** the closest things you can use are ${bold(found)}.`
      : `I searched the **${plural(usable.length, "file")}** and the meetings you can open in **${name}**, and none matched by name.`;
    const left = hidden
      ? ` ${hidden} more ${hidden === 1 ? "belongs" : "belong"} to teams you aren’t in, so I didn’t read ${hidden === 1 ? "it" : "them"}.`
      : "";
    return `${lead}${left}`;
  }
  const mine = scope.files.matched.map((f) => f.name);
  const fromWorkspaces = scope.workspaces.filter((w) => w.matched.length > 0);
  const parts = [
    mine.length ? `In your files: ${bold(mine)}.` : "",
    ...fromWorkspaces.map((w) => `From **${w.workspace.name}**: ${bold(w.matched.map((k) => k.name))}.`),
  ].filter(Boolean);
  if (parts.length) return parts.join(" ");
  const where = scope.workspaces.length
    ? ` and what ${plural(scope.workspaces.length, "workspace")} share with you`
    : "";
  return `I searched the **${plural(scope.files.usable.length, "file")}** you chose for me${where}, and none matched by name.`;
}
