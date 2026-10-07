import { getTranslations } from "next-intl/server";

import { detail } from "@/server/backend-proxy";

import type { ConnectorFieldKey } from "../domain/connectors";

/*
 * Why the demo refuses a request, kept as a code until the answer goes out. It is then worded in the
 * request's interface language (the `knowledgeBaseApi` catalog), as the backend answers in the language it is asked in.
 */

export type Problem =
  | { code: "invalidSettings" | "unknownSource" | "notConnected" }
  | { code: "fieldRequired"; field: ConnectorFieldKey };

export const isProblem = (value: object): value is Problem => "code" in value;

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  const [t, sources] = await Promise.all([
    getTranslations("knowledgeBaseApi"),
    getTranslations("knowledgeBaseSources"),
  ]);
  const message =
    problem.code === "fieldRequired"
      ? t("fieldRequired", { field: sources(`fields.${problem.field}`) })
      : t(problem.code);
  return detail(message, status);
}
