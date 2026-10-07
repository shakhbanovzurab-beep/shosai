import { getTranslations } from "next-intl/server";

import { detail } from "@/server/backend-proxy";

/*
 * Why the demo refuses a billing request, kept as a code until the answer goes out. It is then worded in the
 * request's interface language (the `upgradeApi` catalog), as the backend answers in the language it is asked in.
 */

export type Problem =
  | "choosePlan"
  | "planUnavailable"
  | "salesOnly"
  | "alreadyOnPlan"
  | "singleUser"
  | "paymentsNotConnected"
  | "invalidEmail"
  | "companyRequired"
  | "checkForm";

const PROBLEMS: readonly string[] = [
  "choosePlan",
  "planUnavailable",
  "salesOnly",
  "alreadyOnPlan",
  "singleUser",
  "paymentsNotConnected",
  "invalidEmail",
  "companyRequired",
  "checkForm",
] satisfies Problem[];

/** A validation message that is one of the codes above (the schemas use codes as messages). */
export const isProblem = (message: string | undefined): message is Problem =>
  message !== undefined && PROBLEMS.includes(message);

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  const t = await getTranslations("upgradeApi");
  return detail(t(problem), status);
}

/** The user count a per-user plan accepts, when the request asked for another. */
export async function refuseSeats(min: number, max: number | null) {
  const t = await getTranslations("upgradeApi");
  return detail(max === null ? t("chooseUsersOrMore", { min }) : t("chooseUsers", { min, max }), 422);
}
