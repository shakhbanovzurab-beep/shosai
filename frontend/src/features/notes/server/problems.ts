import { getTranslations } from "next-intl/server";

import { detail } from "@/server/backend-proxy";

import { MY_NOTES_MAX_CHARS } from "../domain/manual-notes";
import { SHARED_COMMENT_MAX } from "../domain/share-link";

/*
 * Why the demo refuses a request, kept as a code until the answer goes out. It is then worded in the
 * request's interface language (the `notesApi` catalog), as the backend answers in the language it is asked in.
 */

export type Problem = "meetingNotFound" | "notesTooLong" | "linkSettingsInvalid" | "commentsClosed" | "commentInvalid";

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  const t = await getTranslations("notesApi");
  switch (problem) {
    case "notesTooLong":
      return detail(t(problem, { max: MY_NOTES_MAX_CHARS }), status);
    case "commentInvalid":
      return detail(t(problem, { max: SHARED_COMMENT_MAX }), status);
    default:
      return detail(t(problem), status);
  }
}
