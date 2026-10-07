/**
 * Where Leo is working: the user's own context, one workspace, or one hub. It decides what Leo may
 * read (a workspace's knowledge only inside that workspace, and only what the member may see; a hub's
 * meetings only inside that hub) and keeps a separate conversation per context, so nothing said in
 * one shows up in another.
 */
export type LeoContext =
  | { kind: "personal" }
  | { kind: "workspace"; id: string; name: string }
  | { kind: "hub"; id: string; name: string };

export const PERSONAL_CONTEXT: LeoContext = { kind: "personal" };

/** "personal", "ws:<id>" or "hub:<id>": the conversation's key. */
export function contextKey(context: LeoContext) {
  if (context.kind === "personal") return "personal";
  return context.kind === "workspace" ? `ws:${context.id}` : `hub:${context.id}`;
}
