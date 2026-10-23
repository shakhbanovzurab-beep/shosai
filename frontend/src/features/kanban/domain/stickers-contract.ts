import type { components } from "@/lib/api/generated/schema";

import type { StopwatchAutomations } from "./time-contract";

/*
 * Поля доски (в коде и API — стикеры, на экране — «поля»): определения, их место на доске и значения задачи.
 * Контракт — TK-D12, план tasks §3.8; поле принадлежит владельцу доски, значение — задаче (KG-D4).
 */

/** Палитра колонок и состояний; кабинет сопоставляет каждому имени цвета Tailwind для светлой и тёмной темы. */
type Schemas = components["schemas"];

export type Color = Schemas["StickerColor"];
export const COLORS = [
  "gray",
  "red",
  "orange",
  "amber",
  "green",
  "teal",
  "blue",
  "violet",
  "pink",
] as const satisfies readonly Color[];

export type SystemStickerId = Schemas["SystemSticker"];
export const SYSTEM_STICKERS = [
  "assignee",
  "due",
  "priority",
  "recurrence",
  "stopwatch",
  "timer",
  "time_tracking",
] as const satisfies readonly SystemStickerId[];

export type CustomKind = Schemas["StickerKind"];
export const CUSTOM_KINDS = ["states", "number", "text"] as const satisfies readonly CustomKind[];
export type StickerKind = SystemStickerId | CustomKind;

export type StickerState = Schemas["StickerStateOut"];

export type StickerOwner = Schemas["PersonOwner"] | Schemas["WorkspaceOwner"];

export type SystemSticker = Omit<Schemas["SystemStickerOut"], "visible">;
export type CustomSticker = Schemas["CustomStickerOut"];
export type Sticker = SystemSticker | CustomSticker;

/** Поле на доске: системное (у секундомера — его автоматизации) или своё, показанное на карточках или нет. */
export type BoardSticker = Schemas["BoardStickerOut"];

export type StickerValue = Schemas["StickerValue"];

/** Автоматизации секундомера доски: их несёт только поле секундомера, у прочих — undefined. */
export const automationsOf = (sticker: BoardSticker | undefined): StopwatchAutomations | undefined =>
  sticker !== undefined && "automations" in sticker ? sticker.automations : undefined;

export type StickerUsage = Schemas["StickerUsageOut"];

export type OwnedSticker = Schemas["OwnedStickerOut"];
export type StickersResponse = Schemas["StickersOut"];

export type NewStateDraft = Omit<Schemas["StateBody"], "id">;
export type NewSticker = Schemas["PlaceNewBody"];

export type PlaceSticker = Schemas["PlaceExistingBody"] | Schemas["PlaceNewBody"];

export type StickerPatch = Schemas["StickerPatchBody"];
export type BoardStickerPatch = Schemas["BoardStickerPatchBody"];

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
