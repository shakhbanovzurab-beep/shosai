/**
 * Where Leo is working: the user's own context, one workspace, one hub, or — in the admin panel — the
 * platform, for its operator. It decides what Leo may read (a workspace's knowledge only inside that
 * workspace, and only what the member may see; a hub's meetings only inside that hub; on the platform its
 * aggregates and nobody's content) and keeps a separate conversation per context, so nothing said in one
 * shows up in another.
 */
export type LeoContext =
  | { kind: "personal" }
  | { kind: "workspace"; id: string; name: string }
  | { kind: "hub"; id: string; name: string }
  | { kind: "platform" };

export const PERSONAL_CONTEXT: LeoContext = { kind: "personal" };
export const PLATFORM_CONTEXT: LeoContext = { kind: "platform" };

/** "personal", "platform", "ws:<id>" or "hub:<id>": the conversation's key. */
export function contextKey(context: LeoContext) {
  if (context.kind === "personal" || context.kind === "platform") return context.kind;
  return context.kind === "workspace" ? `ws:${context.id}` : `hub:${context.id}`;
}
