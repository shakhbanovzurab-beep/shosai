import type { LeoArtifact } from "./artifacts";
import type { LeoProposal } from "./proposals";
import type { LeoSource } from "./sources";

export type LeoMessageStatus = "streaming" | "done" | "stopped" | "error";

export interface LeoStep {
  id: string;
  /** Что делал Leo: имя инструмента (`notes.search`) или код рассуждения; незнакомое слово — общая строка. */
  action: string;
  detail?: string;
  result?: string;
  status: "running" | "done" | "error" | "stopped";
  durationMs?: number;
}

// Only metadata is kept in history; the file contents are sent once, with the message they belong to.
export interface LeoAttachment {
  id: string;
  name: string;
  size: number;
  type: string;
}

export interface LeoMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: LeoMessageStatus;
  attachments?: LeoAttachment[];
  steps?: LeoStep[];
  durationMs?: number;
  /** Источники ответа; маркеры `[n]` в тексте ссылаются на них по порядку. */
  sources?: LeoSource[];
  /** Действия, которые Leo предложил в этом ответе; их состояние дальше ведёт хранилище предложений. */
  proposals?: LeoProposal[];
  /** Результаты, которые читаются отдельно по ссылке: дайджест чата (CF-D11). */
  artifacts?: LeoArtifact[];
  /** Почему ответа нет: код отказа до хода или сбоя хода (`token_limit`, `turn_deadline` …). */
  failure?: LeoFailure;
  /**
   * Оценка ответа человеком (AG-D13): null — не оценён. Ответ без поля не оценивается: его нет в истории сервера
   * (примерный чат, ход ещё идёт).
   */
  feedback?: LeoRating | null;
}

export type LeoRating = "useful" | "not_useful";

/** Код сбоя и, для лимита токенов, какой лимит кончился (`standard_daily_tokens` …). */
export interface LeoFailure {
  code: string;
  limit?: string;
}
