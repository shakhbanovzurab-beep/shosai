import type { StopwatchAutomations } from "./time-contract";

/*
 * Поля доски (в коде и API — стикеры, на экране — «поля»): определения, их место на доске и значения задачи.
 * Контракт — TK-D12, план tasks §3.8; поле принадлежит владельцу доски, значение — задаче (KG-D4).
 */

/** Палитра колонок и состояний; кабинет сопоставляет каждому имени цвета Tailwind для светлой и тёмной темы. */
export const COLORS = ["gray", "red", "orange", "amber", "green", "teal", "blue", "violet", "pink"] as const;
export type Color = (typeof COLORS)[number];

/**
 * Системные поля — собственные поля задачи, они есть на каждой доске. Последние три — время задачи (ADR 0061):
 * выключены, пока доска их не покажет, и не бывают на доске Jira.
 */
export const SYSTEM_STICKERS = [
  "assignee",
  "due",
  "priority",
  "recurrence",
  "stopwatch",
  "timer",
  "time_tracking",
] as const;
export type SystemStickerId = (typeof SYSTEM_STICKERS)[number];

/** Виды своих полей: набор состояний, число, текст. */
export const CUSTOM_KINDS = ["states", "number", "text"] as const;
export type CustomKind = (typeof CUSTOM_KINDS)[number];
export type StickerKind = SystemStickerId | CustomKind;

export type StickerState = { id: string; name: string; color: Color };

/** Владелец своего поля — владелец досок, на которых оно стоит: человек или пространство. */
export type StickerOwner = { user_id: string } | { workspace_id: string };

export type SystemSticker = { id: SystemStickerId; kind: SystemStickerId; name: null; states: [] };
export type CustomSticker = {
  id: string;
  kind: CustomKind;
  name: string;
  /** Только у набора состояний, иначе пусто. */
  states: StickerState[];
  owner: StickerOwner;
};
export type Sticker = SystemSticker | CustomSticker;

/** Поле на доске: системные первыми, затем свои в порядке добавления; у секундомера — его автоматизации. */
export type BoardSticker = Sticker & { visible: boolean; automations?: StopwatchAutomations };

export type StickerValue = { state_id: string } | { number: number } | { text: string };

/** Сколько задач несут значение поля — всего и по состояниям: удаление состояния или поля говорит, что очистит. */
export type StickerUsage = { tasks: number; states: Record<string, number> };

/** Своё поле владельца: доски, где оно стоит, и сколько задач несут его значения. */
export type OwnedSticker = CustomSticker & { boards: { id: string; name: string }[]; usage: StickerUsage };
export type StickersResponse = { items: OwnedSticker[] };

export type NewStateDraft = { name: string; color: Color };
export type NewSticker = { kind: CustomKind; name: string; states?: NewStateDraft[] };

/** Поставить на доску: уже существующее поле владельца или новое. */
export type PlaceSticker = { sticker_id: string } | NewSticker;

/** `states` — полный список: прежние id сохраняют значения, новые приходят без id, пропавшие очищают свои. */
export type StickerPatch = { name?: string; states?: (NewStateDraft & { id?: string })[] };
/** Показ поля на карточках; у секундомера ещё и его автоматизации. */
export type BoardStickerPatch = { visible?: boolean; automations?: StopwatchAutomations };

export const STICKER_NAME_MAX = 40;
export const STATE_NAME_MAX = 40;
export const STATES_MAX = 20;
export const BOARD_STICKERS_MAX = 20;
export const STICKERS_MAX = 100;
export const STICKER_TEXT_MAX = 200;
/** Модуль числа строго меньше; дробная часть — не больше двух знаков. */
export const STICKER_NUMBER_LIMIT = 1e12;

/** Своё поле (не системное): у него есть имя и владелец. */
export const isCustomSticker = <T extends Sticker>(sticker: T): sticker is T & CustomSticker => sticker.name !== null;

export const isSystemSticker = (id: string): id is SystemStickerId =>
  (SYSTEM_STICKERS as readonly string[]).includes(id);

/** Какие системные поля видны на новой доске: тихая доска — исполнитель, срок и приоритет. */
export const NEW_BOARD_SYSTEM_VISIBILITY: Record<SystemStickerId, boolean> = {
  assignee: true,
  due: true,
  priority: true,
  recurrence: false,
  stopwatch: false,
  timer: false,
  time_tracking: false,
};

/** Поля времени задачи: их нет на доске Jira (KG-D8). */
export const TIME_STICKERS = ["stopwatch", "timer", "time_tracking"] as const satisfies readonly SystemStickerId[];
export type TimeStickerId = (typeof TIME_STICKERS)[number];
export const isTimeSticker = (id: string): id is TimeStickerId => (TIME_STICKERS as readonly string[]).includes(id);
