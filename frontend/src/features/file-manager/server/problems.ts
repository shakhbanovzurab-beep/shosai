import { getLocale, getTranslations } from "next-intl/server";

import { formatBytes } from "@/i18n/format-units";
import { detail } from "@/server/backend-proxy";

/*
 * Why the demo refuses a request, kept as a code (with its numbers) until the answer goes out. It is then
 * worded in the request's interface language (the `fileManagerApi` catalog), as the backend answers in the
 * language it is asked in.
 */

export type Problem =
  | {
      code:
        | "fileGone"
        | "folderGone"
        | "chooseFile"
        | "notUsedByLeo"
        | "shareFirst"
        | "fileNameRequired"
        | "folderNameRequired"
        | "nameSlash"
        | "invalidRequest";
    }
  | { code: "tooManyFiles"; max: number }
  | { code: "nameTooLong"; max: number }
  | { code: "tooLarge"; name: string; bytes: number }
  | { code: "overLeoLimit"; bytes: number };

export const isProblem = (value: object): value is Problem => "code" in value;

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  const [t, locale] = await Promise.all([getTranslations("fileManagerApi"), getLocale()]);
  let message: string;
  if (problem.code === "tooManyFiles" || problem.code === "nameTooLong") message = t(problem.code, problem);
  else if (problem.code === "tooLarge")
    message = t("tooLarge", { name: problem.name, size: formatBytes(locale, problem.bytes) });
  else if (problem.code === "overLeoLimit") message = t("overLeoLimit", { limit: formatBytes(locale, problem.bytes) });
  else message = t(problem.code);
  return detail(message, status);
}

/** Words a copy's name in the request's language: "Report" → "Report copy". */
export async function copyWording() {
  const t = await getTranslations("fileManagerApi");
  return (base: string) => t("copyName", { name: base });
}
