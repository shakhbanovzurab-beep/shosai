import { getLocale, getTranslations } from "next-intl/server";

import { formatBytes } from "@/i18n/format-units";
import { detail } from "@/server/backend-proxy";

import { BODY_MAX, MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS } from "../domain/contract";

/*
 * Why the demo refuses a request, kept as a code until the answer goes out. It is then worded in the
 * request's interface language (the `pagesApi` catalog), as the backend answers in the language it is asked in.
 */

export type Problem =
  | { code: "notMultipart" }
  | { code: "emptyMessage" }
  | { code: "messageTooLong" }
  | { code: "tooManyFiles" }
  | { code: "fileTooBig"; name: string }
  | { code: "subjectRequired" }
  | { code: "topicRequired" }
  | { code: "detailsRequired" }
  | { code: "ticketNotFound" }
  | { code: "invalidUpdate" };

/** The words for a problem in the request's interface language. */
async function word(problem: Problem): Promise<string> {
  const t = await getTranslations("pagesApi");
  switch (problem.code) {
    case "messageTooLong":
      return t("messageTooLong", { max: BODY_MAX });
    case "tooManyFiles":
      return t("tooManyFiles", { max: MAX_ATTACHMENTS });
    case "fileTooBig":
      return t("fileTooBig", { name: problem.name, size: formatBytes(await getLocale(), MAX_ATTACHMENT_BYTES) });
    default:
      return t(problem.code);
  }
}

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  return detail(await word(problem), status);
}
