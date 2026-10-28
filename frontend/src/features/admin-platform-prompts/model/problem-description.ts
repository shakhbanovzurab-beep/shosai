import type { ReactNode } from "react";

import { apiErrorDescription } from "@/lib/api/error-description";
import { ApiError } from "@/lib/api/errors";

import type { PlatformConfig } from "../domain/contract";
import { problemText } from "../domain/problems";

/** Описание ошибки запроса для тоста: слова админки для кода, иначе общее описание с id запроса. */
export function problemOf(error: unknown, config: PlatformConfig): ReactNode {
  if (error instanceof ApiError && error.code) {
    const text = problemText({ code: error.code, params: error.params }, config);
    if (text) return text;
  }
  return apiErrorDescription(error);
}
