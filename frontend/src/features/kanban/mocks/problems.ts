import { detail, getTranslations } from "@/mocks/runtime";

/*
 * Why the demo refuses a request, kept as a code until the answer goes out. It is then worded in the
 * request's interface language (the `kanbanApi` catalog), as the backend answers in the language it is asked in.
 */

export type Problem =
  | "boardNotFound"
  | "taskNotFound"
  | "columnNotFound"
  | "boardChanged"
  | "managedInJira"
  | "reconnectJira"
  | "firstSync"
  | "jiraDisconnected"
  | "connectJiraFirst"
  | "jiraBoardUnavailable"
  | "jiraBoardSynced"
  | "notJiraBoard"
  | "jiraBoardWorkspaceTasks"
  | "workspaceTaskCopy"
  | "workspaceTaskDelete"
  | "boardNameRequired"
  | "boardNameTooLong"
  | "taskTitleRequired"
  | "invalidRequest";

/** Turns a problem into the words the user reads. */
export type Wording = (problem: Problem) => string;

/** The words for problems in the request's interface language. */
export async function problemWording(): Promise<Wording> {
  const t = await getTranslations("kanbanApi");
  return (problem) => t(problem);
}

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  const word = await problemWording();
  return detail(word(problem), status);
}
