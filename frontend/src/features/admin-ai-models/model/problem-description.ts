import type { ReactNode } from "react";

import { apiErrorDescription } from "@/lib/api/error-description";
import { ApiError } from "@/lib/api/errors";

import { problemText } from "../domain/problems";

/** Описание ошибки запроса для тоста: слова админки для кода, иначе общее описание с id запроса. */
export function problemOf(error: unknown): ReactNode {
  if (error instanceof ApiError) {
    const text = problemText(error.code);
    if (text) return text;
  }
  return apiErrorDescription(error);
}
