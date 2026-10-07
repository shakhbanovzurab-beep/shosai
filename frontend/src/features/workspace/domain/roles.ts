import type { Member, Project, WorkspaceState } from "./contract";
import { firstName } from "./people";

export const isAdmin = (member: Pick<Member, "role">) => member.role === "owner" || member.role === "admin";

/** The signed-in member; the API always includes them in `members`. */
export function findMe(state: WorkspaceState): Member {
  const me = state.members.find((m) => m.id === state.me_id);
  if (!me) throw new Error("The signed-in member is missing from the workspace.");
  return me;
}

/** What the signed-in member may do in the workspace as a whole. */
export function permissionsOf(state: WorkspaceState) {
  const me = findMe(state);
  const admin = isAdmin(me);
  return {
    me,
    admin,
    invite: admin || state.workspace.sharing.members_can_invite,
    managePeople: admin,
    manageTeams: admin,
    editSettings: admin,
    manageBilling: me.role === "owner",
    deleteWorkspace: me.role === "owner",
    leave: me.role !== "owner",
  };
}

export type Permissions = ReturnType<typeof permissionsOf>;

/** A project's lead and admins edit or delete it; everyone can add tasks to it. */
export const canEditProject = (me: Member, project: Pick<Project, "lead_id">) =>
  isAdmin(me) || project.lead_id === me.id;

/** Admins change everyone's role except the owner's and their own. */
export const canManageMember = (me: Member, target: Member) =>
  isAdmin(me) && target.role !== "owner" && target.id !== me.id;

/** Who answers questions about access: the owner, then any admin. */
export function adminContact(state: WorkspaceState) {
  return (
    state.members.find((m) => m.role === "owner") ?? state.members.find((m) => m.role === "admin") ?? state.members[0]
  );
}

/** Who to ask about a control that is off for the signed-in member, by first name; null when nobody can help. */
export function adminContactName(state: WorkspaceState) {
  const contact = adminContact(state);
  return contact ? firstName(contact.name) : null;
}
