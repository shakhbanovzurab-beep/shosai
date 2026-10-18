"use client";

import type { ReactNode } from "react";

import { apiErrorDescription } from "@/lib/api/error-description";

import { PartFailedError } from "../api/uploads-api";
import { fileProblemOf } from "../domain/problems";
import { UploadRejectedError } from "./uploads";
import type { FileActionWords } from "./words";

/** A failure as the user reads it: the files API's known codes and the upload's own failures in their words. */
export function describeError(error: unknown, { t, bytes }: FileActionWords): ReactNode {
  if (error instanceof UploadRejectedError) return t("problems.upload_rejected");
  if (error instanceof PartFailedError) return t("problems.upload_interrupted");
  const problem = fileProblemOf(error);
  if (problem === null) return apiErrorDescription(error);
  if (problem.code === "leo_limit") return t("problems.leo_limit", { limit: bytes(problem.limitBytes ?? 0) });
  return t(`problems.${problem.code}`);
}
