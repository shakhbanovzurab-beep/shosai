import type { LeoProposal } from "../domain/proposals";
import type { LeoMessage } from "../domain/types";

/*
 * Что панель Leo получает от разговора, откуда бы он ни шёл: с настоящего API (`useAgentChat`) или с примерного
 * `/api/leo`, на котором остаются хаб и админка до своих шагов (`useLeoChat`).
 */
export interface LeoChat {
  readonly messages: LeoMessage[];
  readonly isBusy: boolean;
  /** Разговор ещё загружается: панель показывает заготовку, а не приветствие. */
  readonly loading: boolean;
  /** Ответ Leo, каким он закончился; undefined — вопрос не ушёл. */
  readonly send: (content: string, files?: File[]) => Promise<LeoMessage | undefined>;
  readonly stop: () => void;
  readonly regenerate: () => void;
  readonly editLast: (content: string) => void;
  readonly addProposal: (messageId: string, proposal: LeoProposal) => void;
  readonly reset: () => void;
  /** Более ранние сообщения треда, если они есть на сервере. */
  readonly earlier?: { readonly available: boolean; readonly loading: boolean; readonly load: () => void };
  /** Можно ли приложить файлы к вопросу: к Leo на API — с загрузками для Leo (шаг 12). */
  readonly attachments: boolean;
}
