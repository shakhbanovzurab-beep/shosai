import type { RecencyGroup } from "./format";

/** Какую часть библиотеки читать: id папки или `none` — встречи без папки; не задана — все встречи. */
export type LibraryFolder = string | "none";

/** Где записи Leo о встрече: ещё нет, пишутся, готовы или не вышли. */
export type NotesState = "none" | "processing" | "ready" | "failed";

/** Встреча, какой её показывает библиотека: карточка из `GET /v1/notes`. */
export interface MeetingCard {
  id: string;
  title: string;
  status: "active" | "completed" | "failed";
  /** Записана в приложении (`live`) или загружена файлом (`import`). */
  source: "live" | "import";
  /** Время начала в ISO. */
  startedAt: string;
  durationMinutes: number;
  /** Своя встреча человека; чужая пришла из рабочего пространства. */
  owned: boolean;
  /** Папка владельца; у чужой встречи её не видно. */
  folderId?: string;
  participantNames: string[];
  participantCount: number;
  summary: string | null;
  keyPoints: string[];
  firstDecision: string | null;
  /** Сколько задач в записи Leo. */
  actionItems: number;
  notes: NotesState;
}

/** Встречи под одним заголовком библиотеки, например сегодняшние. */
export interface CardGroup {
  recency: RecencyGroup;
  items: MeetingCard[];
}

/** Сколько встреч в библиотеке: все доступные и свои по папкам. */
export interface LibraryCounts {
  all: number;
  byFolder: ReadonlyMap<string, number>;
}

/** Встреча ещё идёт или её записи пишутся: библиотека опрашивает сервер, пока это так. */
export const isBusyCard = (card: Pick<MeetingCard, "status" | "notes">) =>
  card.status === "active" || card.notes === "processing";
