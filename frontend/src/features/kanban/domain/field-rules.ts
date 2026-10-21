import {
  type CustomKind,
  type NewStateDraft,
  STATE_NAME_MAX,
  STATES_MAX,
  STICKER_NAME_MAX,
  type StickerUsage,
  type StickerValue,
} from "./stickers-contract";
import type { Card } from "./tasks-contract";

/* Правила полей доски, общие для настроек и карточек (KG-D4, TK-D12). */

/** Значения поля уходят с карточек доски: поле снято с неё или удалено (`keep` оставляет часть состояний). */
export function cardsWithout(
  cards: Record<string, Card>,
  stickerId: string,
  keep: (stateId: string) => boolean = () => false,
): Record<string, Card> {
  const next: Record<string, Card> = {};
  for (const [id, card] of Object.entries(cards)) {
    const value = card.values[stickerId];
    const stays = value !== undefined && "state_id" in value && keep(value.state_id);
    if (value === undefined || stays) next[id] = card;
    else {
      const { [stickerId]: _gone, ...values } = card.values;
      next[id] = { ...card, values };
    }
  }
  return next;
}

/** Значения поля возвращаются на карточки, с которых их сняли (отказ сервера). */
export function cardsWithValues(
  cards: Record<string, Card>,
  stickerId: string,
  values: Record<string, StickerValue>,
): Record<string, Card> {
  const next = { ...cards };
  for (const [id, value] of Object.entries(values)) {
    const card = next[id];
    if (card) next[id] = { ...card, values: { ...card.values, [stickerId]: value } };
  }
  return next;
}

/** Значения поля на карточках доски по id карточки — чтобы вернуть их, если снять поле не вышло. */
export const valuesOn = (cards: Record<string, Card>, stickerId: string): Record<string, StickerValue> =>
  Object.fromEntries(
    Object.entries(cards).flatMap(([id, card]) => {
      const value = card.values[stickerId];
      return value ? [[id, value]] : [];
    }),
  );

/** Сколько задач потеряют значение, если убрать эти состояния. */
export const clearedBy = (usage: StickerUsage, removedStateIds: string[]) =>
  removedStateIds.reduce((sum, id) => sum + (usage.states[id] ?? 0), 0);

export type FieldDraftProblem =
  | "name_required"
  | "name_too_long"
  | "states_required"
  | "state_name_required"
  | "state_names_repeat"
  | "states_full";

/** Что мешает сохранить поле, или null: имя, а у набора — хотя бы одно состояние с непустыми разными именами. */
export function fieldDraftProblem(kind: CustomKind, name: string, states: NewStateDraft[]): FieldDraftProblem | null {
  const trimmed = name.trim();
  if (!trimmed) return "name_required";
  if (trimmed.length > STICKER_NAME_MAX) return "name_too_long";
  if (kind !== "states") return null;
  if (states.length === 0) return "states_required";
  if (states.length > STATES_MAX) return "states_full";
  const names = states.map((state) => state.name.trim());
  if (names.some((stateName) => !stateName || stateName.length > STATE_NAME_MAX)) return "state_name_required";
  const seen = new Set(names.map((stateName) => stateName.toLocaleLowerCase()));
  return seen.size === names.length ? null : "state_names_repeat";
}
