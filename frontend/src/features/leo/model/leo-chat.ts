import type { LeoProposal } from "../domain/proposals";
import type { LeoMessage } from "../domain/types";
import type { LeoThreads } from "./use-agent-threads";
import type { VoiceTarget } from "./voice/voice-socket";

/*
 * Что панель Leo получает от разговора, откуда бы он ни шёл: с настоящего API (`useAgentChat`) или с примерного
 * `/api/leo`, на котором остаётся хаб до своего шага (`useLeoChat`, agent шаг 20).
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
  /** Можно ли приложить файлы к вопросу: к Leo человека на API — загрузками `leo_attachment` (шаг 12 агента). */
  readonly attachments: boolean;
  /** Чей разговор: настройки Leo (Settings › Leo — голос, язык ответа) есть только у человека. */
  readonly owner: "person" | "operator";
  /**
   * Тред человека, у которого память может предложить кандидата: строка под ответом читает их по нему (MM-D1).
   * Нет у оператора и у примерного чата.
   */
  readonly memoryThreadId?: string | null;
  /** «Недавние чаты» пространства; у примерного чата их нет. */
  readonly threads?: LeoThreads;
  /**
   * Голосовой режим (ADR 0070): куда говорить и как показать реплики после разговора — тред, в который
   * их записал сервер. Только у разговора человека на API; у оператора и у примерного чата голоса нет.
   */
  readonly voice?: { readonly target: VoiceTarget; readonly refresh: (threadId: string | null) => void };
}
