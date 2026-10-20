"use client";

import type { ReactNode } from "react";

import { apiErrorDescription } from "@/lib/api/error-description";
import { UploadRejectedError } from "@/lib/uploads/upload-file";
import { PartFailedError } from "@/lib/uploads/uploads-api";

import { noteProblemOf } from "../domain/problems";
import type { NotesWords } from "./words";

/** Ошибка, как её читает человек: известные коды заметок и сбои загрузки — его словами, прочее — текстом сервера. */
export function describeNoteError(error: unknown, t: NotesWords): ReactNode {
  if (error instanceof UploadRejectedError) return t("problems.upload_rejected");
  if (error instanceof PartFailedError) return t("problems.upload_interrupted");
  const problem = noteProblemOf(error);
  return problem === null ? apiErrorDescription(error) : t(`problems.${problem}`);
}
