import { ApiError } from "@/lib/api/errors";

/**
 * Почему API заметок отказал: коды бэкенд-среза `notes` (ADR 0008). Интерфейс называет их на языке человека;
 * любой другой код оставляет текст сервера и id запроса для поддержки.
 */
export const NOTE_PROBLEMS = [
  "meeting_not_found",
  "meeting_not_yours",
  "meeting_active",
  "meeting_read_only",
  "company_meeting_has_no_folder",
  "folder_not_found",
  "folder_name_required",
  "folder_name_too_long",
  "template_not_found",
  "template_not_shipped",
  "template_builtin_read_only",
  "templates_limit_reached",
  "template_name_required",
  "template_name_too_long",
  "template_description_too_long",
  "template_section_title_too_long",
  "template_sections_required",
  "template_section_repeated",
  "notes_not_ready",
  "notes_too_long",
  "participant_email_invalid",
  "participants_limit_reached",
  "participant_not_found",
  "participant_not_removable",
  "upload_not_claimable",
  "meetings_not_kept",
  "private_meeting",
] as const;

export type NoteProblem = (typeof NOTE_PROBLEMS)[number];

/** Известная причина отказа, или null для любой другой ошибки. */
export function noteProblemOf(error: unknown): NoteProblem | null {
  if (!(error instanceof ApiError)) return null;
  return NOTE_PROBLEMS.find((problem) => problem === error.code) ?? null;
}

/** Почему прогон не написал заметки: коды стадий, которые не повторяются; остальные — общая неудача. */
export const RUN_FAILURES = [
  "transcript_empty",
  "upload_exceeds_minutes",
  "recording_too_long",
  "unsupported_audio_format",
  "media_unreadable",
  "consent_required",
  "content_refused",
] as const;

export type RunFailure = (typeof RUN_FAILURES)[number] | "other";

export const runFailureOf = (code: string | null): RunFailure =>
  RUN_FAILURES.find((failure) => failure === code) ?? "other";

/** Ошибка API с этим кодом: так читатели отличают «ещё нет» от сбоя. */
export const isApiCode = (error: unknown, code: string) => error instanceof ApiError && error.code === code;
