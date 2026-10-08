import { detail, getLocale, getTranslations } from "@/mocks/runtime";

import { SEATS_MIN } from "../domain/contract";

/*
 * Why the demo refuses a request, kept as a code until the answer goes out. It is then worded in the
 * request's interface language (the `workspaceApi` catalog), as the backend answers in the language it is
 * asked in. Validation problems are codes too: the schemas use them as their messages.
 */

/** Problems a person can fix in the form they sent. */
export const VALIDATION_PROBLEMS = [
  "workspaceNameRequired",
  "teamNameRequired",
  "projectNameRequired",
  "taskTitleRequired",
  "sourceNameRequired",
  "seatsTooFew",
  "domainInvalid",
  "emailsInvalid",
  "emailsRequired",
  "pickTeamToShare",
  "pickTeam",
  "linkInvalid",
] as const;

export type ValidationProblem = (typeof VALIDATION_PROBLEMS)[number];

export type Problem =
  | ValidationProblem
  | "checkForm"
  | "notMember"
  | "suspended"
  | "adminsConnectSources"
  | "adminsRemovePeople"
  | "adminsChangeSettings"
  | "adminsSeeUsage"
  | "adminsCreateTeams"
  | "adminsEditTeams"
  | "adminsDeleteTeams"
  | "adminsInvitePeople"
  | "adminsInviteAdmins"
  | "adminsRevokeInvitation"
  | "adminsAddToTeam"
  | "sendFilesAsForm"
  | "chooseFile"
  | "teamGone"
  | "teamsGone"
  | "projectGone"
  | "knowledgeGone"
  | "knowledgeChangeDenied"
  | "knowledgeRemoveDenied"
  | "allAlreadyInvited"
  | "invitationGone"
  | "personGone"
  | "peopleGone"
  | "leadGone"
  | "roleChangeDenied"
  | "ownerCantBeRemoved"
  | "meetingNotFound"
  | "recordingNotFound"
  | "meetingShareDenied"
  | "meetingUnshareDenied"
  | "projectEditDenied"
  | "projectDeleteDenied"
  | "taskNotFound"
  | "ownerOnlyDelete"
  | "ownerCantLeave"
  | "teamHasKnowledge";

export type ApiWords = Awaited<ReturnType<typeof getTranslations<"workspaceApi">>>;

/** A refusal that needs values in its words ("Only 2 seats left"): written with the request's words and language. */
export type Wording = (t: ApiWords, locale: string) => string;

function word(t: ApiWords, problem: Problem) {
  if (problem === "seatsTooFew") return t("seatsTooFew", { count: SEATS_MIN });
  return t(problem);
}

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem | Wording, status: number) {
  const [t, locale] = await Promise.all([getTranslations("workspaceApi"), getLocale()]);
  return detail(typeof problem === "function" ? problem(t, locale) : word(t, problem), status);
}

const isValidationProblem = (message: string | undefined): message is ValidationProblem =>
  (VALIDATION_PROBLEMS as readonly string[]).includes(message ?? "");

/** The first validation problem of a body, or "checkForm" when the request itself is malformed. */
export function validationProblem(message: string | undefined): Problem {
  return isValidationProblem(message) ? message : "checkForm";
}
