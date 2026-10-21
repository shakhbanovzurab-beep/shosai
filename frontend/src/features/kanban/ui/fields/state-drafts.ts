import { COLORS, type Color, type CustomSticker, type StickerPatch } from "../../domain/stickers-contract";

/** Состояние в правке: `id` у прежнего (его значения сохраняются), `key` — для списка, пока id нет. */
export type StateDraft = { key: string; id?: string; name: string; color: Color };

export const newStateDraft = (index: number): StateDraft => ({
  key: crypto.randomUUID(),
  name: "",
  color: COLORS[(index + 6) % COLORS.length],
});

export const draftsOf = (sticker: CustomSticker): StateDraft[] =>
  sticker.states.map((state) => ({ key: state.id, ...state }));

/** Состояния для API: полным списком, прежние с id, новые без него. */
export const statesOf = (drafts: StateDraft[]): NonNullable<StickerPatch["states"]> =>
  drafts.map(({ id, name, color }) => ({ ...(id ? { id } : {}), name: name.trim(), color }));

/** Id прежних состояний, которых в правке больше нет. */
export function removedStates(sticker: CustomSticker | null, drafts: StateDraft[]): string[] {
  const kept = new Set(drafts.flatMap((draft) => (draft.id ? [draft.id] : [])));
  return (sticker?.states ?? []).filter((state) => !kept.has(state.id)).map((state) => state.id);
}
